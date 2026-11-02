#!/usr/bin/env bash
#
# Wrapper for running the spellcheck script as a precommit hook to find `uv`
#
# AI CITATION: This file includes content generated with the assistance of
# Claude Opus 4.6, a generative AI tool. Claude Opus 4.6 was used to generate
# and modify the source code accompanying documentation using solely public
# information. All AI-generated content has been reviewed/edited by the MITRE
# team to ensure accuracy and followed MITRE's generative AI use guidelines.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v uv &>/dev/null; then
    exec uv run "$SCRIPT_DIR/spellcheck.py" "$@"
fi

# Common install locations
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$candidate" ]]; then
        exec "$candidate" run "$SCRIPT_DIR/spellcheck.py" "$@"
    fi
done

echo "error: uv not found" >&2
exit 1