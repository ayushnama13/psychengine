#!/usr/bin/env bash
# Launch PsychEngine dev server.
set -e
cd "$(dirname "$0")/../.."  # repo root; ./psychengine is a symlink to psychengine-web so the package imports resolve
exec ../.venv/bin/python -m psychengine.web.app
