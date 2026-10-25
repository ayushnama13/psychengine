"""AI router. Tries Cerebras → Groq → Ollama. Rotates keys on rate limit.

Engines are OpenAI-compatible. Single chat() entrypoint.
Caches by (feature, request_hash) to ai_cache table.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.config import (
    cerebras_keys, groq_keys,
    CEREBRAS_MODEL, GROQ_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL,
)
from psychengine.db import connect


CEREBRAS_BASE = "https://api.cerebras.ai/v1"
GROQ_BASE = "https://api.groq.com/openai/v1"


class AIError(RuntimeError):
    pass


def _cache_key(feature: str, request_hash: str) -> str:
    return f"{feature}:{request_hash}"


def _hash_request(messages, model, json_mode, temperature) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(messages, sort_keys=True).encode())
    h.update(model.encode())
    h.update(f"{json_mode}:{temperature}".encode())
    return h.hexdigest()


def _cache_get(feature: str, req_hash: str):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT response, engine_used FROM ai_cache WHERE cache_key = ?",
            (_cache_key(feature, req_hash),),
        ).fetchone()
        if row:
            return row["response"], row["engine_used"]
    finally:
        conn.close()
    return None


def _cache_put(feature: str, req_hash: str, response: str, engine: str):
    conn = connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache(cache_key, feature, request_hash, response, engine_used) "
            "VALUES(?,?,?,?,?)",
            (_cache_key(feature, req_hash), feature, req_hash, response, engine),
        )
        conn.commit()
    finally:
        conn.close()


def _log(feature: str, engine: str, key_idx: int | None, ptok: int, ctok: int, dur_ms: int, status: str, err: str | None = None):
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO ai_api_log(feature, engine, key_index, prompt_tokens, completion_tokens, duration_ms, status, error) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (feature, engine, key_idx, ptok, ctok, dur_ms, status, err),
        )
        conn.commit()
    finally:
        conn.close()


def _try_openai_compat(base_url: str, api_key: str, model: str, messages, json_mode: bool, temperature: float, max_tokens: int):
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0)
    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    ptok = getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0
    ctok = getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0
    return text, ptok, ctok


def _try_ollama(messages, json_mode: bool, temperature: float, max_tokens: int):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"
    r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"], 0, 0


def chat(
    feature: str,
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    use_cache: bool = True,
    prefer: str = "auto",  # auto | cerebras | groq | ollama
) -> tuple[str, str]:
    """Returns (response_text, engine_used). Raises AIError if all fail."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    req_hash = _hash_request(messages, prefer, json_mode, temperature)
    if use_cache:
        cached = _cache_get(feature, req_hash)
        if cached:
            return cached

    errors: list[str] = []

    def try_engine(engine_name: str, base: str | None, model: str, keys: list[str] | None):
        nonlocal errors
        if engine_name == "ollama":
            t0 = time.time()
            try:
                text, p, c = _try_ollama(messages, json_mode, temperature, max_tokens)
                _log(feature, "ollama", None, p, c, int((time.time()-t0)*1000), "ok")
                return text
            except Exception as e:
                errors.append(f"ollama: {e}")
                _log(feature, "ollama", None, 0, 0, int((time.time()-t0)*1000), "err", str(e))
                return None
        assert keys is not None and base is not None
        for idx, k in enumerate(keys):
            t0 = time.time()
            try:
                text, p, c = _try_openai_compat(base, k, model, messages, json_mode, temperature, max_tokens)
                _log(feature, engine_name, idx, p, c, int((time.time()-t0)*1000), "ok")
                return text
            except RateLimitError as e:
                errors.append(f"{engine_name}#{idx} rate-limit")
                _log(feature, engine_name, idx, 0, 0, int((time.time()-t0)*1000), "rate_limit", str(e))
                continue
            except (APIStatusError, APIConnectionError) as e:
                errors.append(f"{engine_name}#{idx} {type(e).__name__}: {e}")
                _log(feature, engine_name, idx, 0, 0, int((time.time()-t0)*1000), "err", str(e))
                continue
            except Exception as e:
                errors.append(f"{engine_name}#{idx} {type(e).__name__}: {e}")
                _log(feature, engine_name, idx, 0, 0, int((time.time()-t0)*1000), "err", str(e))
                continue
        return None

    order: list[tuple[str, str | None, str, list[str] | None]] = []
    cere = cerebras_keys()
    gro = groq_keys()
    if prefer == "cerebras" or prefer == "auto":
        if cere:
            order.append(("cerebras", CEREBRAS_BASE, CEREBRAS_MODEL, cere))
    if prefer == "groq" or prefer == "auto":
        if gro:
            order.append(("groq", GROQ_BASE, GROQ_MODEL, gro))
    if prefer == "ollama" or prefer == "auto":
        order.append(("ollama", None, OLLAMA_MODEL, None))

    for engine_name, base, model, keys in order:
        out = try_engine(engine_name, base, model, keys)
        if out is not None:
            if use_cache:
                _cache_put(feature, req_hash, out, engine_name)
            return out, engine_name

    raise AIError(f"All engines failed. errors: {errors[:8]}")


def parse_json(text: str) -> Any:
    """Tolerant JSON parser. Strips markdown fences, finds first {...} or [...]."""
    text = text.strip()
    if text.startswith("```"):
        # strip fence
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # find first { or [ and last matching
    for open_c, close_c in [("{", "}"), ("[", "]")]:
        s = text.find(open_c)
        e = text.rfind(close_c)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from: {text[:300]}")
