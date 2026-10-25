#!/usr/bin/env bash
# Phase 1+2 full pipeline.
# Usage: bash scripts/pipeline.sh [ingest|extract|cluster|deps|decay|all]
set -e
cd "$(dirname "$0")/../.."  # repo root; ./psychengine is a symlink to psychengine-web so the package imports resolve
PY=../.venv/bin/python

case "${1:-help}" in
  ingest)   $PY -m psychengine.ingest.cli all ;;
  extract)  $PY -m psychengine.taxonomy.extract_concepts ;;
  cluster)  $PY -m psychengine.taxonomy.cluster ;;
  deps)     $PY -m psychengine.taxonomy.dependencies ;;
  decay)    $PY -m psychengine.engine.decay ;;
  stats)    $PY -m psychengine.ingest.cli stats ;;
  all)
    $PY -m psychengine.ingest.cli all --yes
    $PY -m psychengine.taxonomy.extract_concepts
    $PY -m psychengine.taxonomy.cluster
    $PY -m psychengine.taxonomy.dependencies
    $PY -m psychengine.engine.decay
    $PY -m psychengine.ingest.cli stats
    ;;
  *)
    echo "Usage: $0 [ingest|extract|cluster|deps|decay|stats|all]"
    exit 1 ;;
esac
