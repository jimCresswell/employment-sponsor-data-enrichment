#!/usr/bin/env bash
set -euo pipefail

uv run format-check
uv run typecheck
uv run lint
uv run test
uv run coverage
