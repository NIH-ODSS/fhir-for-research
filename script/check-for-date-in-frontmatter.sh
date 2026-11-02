#!/usr/bin/env bash
# .git/hooks/pre-commit — Ensure modules/**/*.qmd have `date` in frontmatter

# AI CITATION: This file includes content generated with the assistance of
# Claude Opus 4.6, a generative AI tool. Claude Opus 4.6 was used to generate
# and modify the source code accompanying documentation using solely public
# information. All AI-generated content has been reviewed/edited by the MITRE
# team to ensure accuracy and followed MITRE's generative AI use guidelines.

files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^modules/.*\.qmd$')

if [ -z "$files" ]; then
  exit 0
fi

errors=()

for f in $files; do
  # Extract YAML frontmatter (between first pair of ---)
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$f" | sed '1d;$d')

  if ! echo "$frontmatter" | grep -qE '^date:'; then
    errors+=("$f")
  fi
done

if [ ${#errors[@]} -gt 0 ]; then
  echo "ERROR: The following .qmd files are missing a 'date' field in frontmatter:"
  for f in "${errors[@]}"; do
    echo "  - $f"
  done
  exit 1
fi

exit 0