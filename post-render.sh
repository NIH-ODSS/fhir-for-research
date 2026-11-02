#!/bin/sh

set -eu

# The browser reads this external script, so generation can follow HTML rendering.
if [ "${QUARTO_PROJECT_RENDER_ALL:-}" = "1" ]; then
  echo "Full project render detected, updating role maps..."
  UV_CACHE_DIR=.uv-cache uv run script/update-module-role-maps.py
  mkdir -p "$QUARTO_PROJECT_OUTPUT_DIR/modules"
  cp modules/mappings.js "$QUARTO_PROJECT_OUTPUT_DIR/modules/mappings.js"
fi
