#!/bin/sh


# see https://quarto.org/docs/projects/scripts.html#pre-and-post-render
# avoids conversion on partial render in local development
if [ "$QUARTO_PROJECT_RENDER_ALL" = "1" ]; then
  echo "Full project render detected, running pre-render script..."
  uv run python script/update-module-role-maps.py
fi
