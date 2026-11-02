# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyspellchecker",
# ]
# ///
"""
Spell check all .qmd files in a Quarto website project.

Usage:
    uv run script/spellcheck.py [ROOT_DIR] [--wordlist PATH] [--add-unknown] [--add-all] [--summary]
    uv run script/spellcheck.py --files FILE [FILE ...]

Arguments:
    ROOT_DIR        Project root to search (default: current directory)

Options:
    --files FILE     Check specific files instead of scanning a directory
    --wordlist PATH  Path to custom wordlist file (default: script/wordlist.txt)
    --add-unknown    Interactively prompt to add unknown words to the wordlist
    --add-all        Add all unknown words to the wordlist without prompting
    --summary        Only show summary counts, not individual words
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from spellchecker import SpellChecker

# ---------------------------------------------------------------------------
# Prose extraction
# ---------------------------------------------------------------------------

# Patterns to strip from prose lines before spell checking
INLINE_CODE_RE = re.compile(r"`[^`]+`")
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\S+\.(?:com|org|net|edu|gov|io|dev|co|html?|xml|json|yaml|yml|css|js|py|qmd|md|pdf)\b\S*")
HTML_TAG_RE = re.compile(r"<[^>]+>")
QUARTO_CROSSREF_RE = re.compile(r"@(fig|tbl|sec|eq|lst|thm|lem|cor|prp|cnj|def|exm|exr|tip|nte|wrn|imp)-[\w-]+")
QUARTO_SHORTCODE_RE = re.compile(r"\{\{<[^>]+>\}\}")
MARKDOWN_LINK_URL_RE = re.compile(r"\]\([^)]+\)")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")
HUGO_SHORTCODE_RE = re.compile(r"\{\{%.*?%\}\}")
DIVFENCE_RE = re.compile(r"^:{3,}.*$")
# @CiteKey_Author_Year or [@CiteKey; @CiteKey2]
CITE_KEY_RE = re.compile(r"\[?@[\w_][\w_:-]*(?:\s*;\s*@[\w_][\w_:-]*)*\]?")


def strip_noise(line: str) -> str:
    """Remove inline code, URLs, HTML tags, cross-refs, etc."""
    for pattern in (
        INLINE_CODE_RE,
        URL_RE,
        HTML_TAG_RE,
        CITE_KEY_RE,
        QUARTO_CROSSREF_RE,
        QUARTO_SHORTCODE_RE,
        MARKDOWN_LINK_URL_RE,
        FOOTNOTE_REF_RE,
        HUGO_SHORTCODE_RE,
        DIVFENCE_RE,
    ):
        line = pattern.sub(" ", line)
    return line


def extract_prose(text: str) -> list[tuple[int, str]]:
    """Return (line_number, text) for prose lines, skipping YAML frontmatter,
    code blocks, and raw HTML blocks."""
    lines = text.splitlines()
    in_yaml = False
    in_code = False
    result: list[tuple[int, str]] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # YAML frontmatter (only at the very start of the file)
        if i == 1 and stripped == "---":
            in_yaml = True
            continue
        if in_yaml:
            if stripped == "---" or stripped == "...":
                in_yaml = False
            continue

        # Fenced code blocks (``` or ~~~)
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue

        # Skip lines that are pure comments or shortcodes
        if stripped.startswith("<!--") or stripped.startswith("{{<"):
            continue

        # Skip bibliography / author-list lines:
        # Lines with multiple "Surname AB," patterns (≥2 occurrences) or ending in "et al."
        if (
            re.search(r"et\s+al\.?\s*$", stripped)
            or len(re.findall(r"[A-Z][a-z]+\s+[A-Z]{1,3}[,.]", stripped)) >= 2
        ):
            continue

        result.append((i, strip_noise(line)))

    return result


# ---------------------------------------------------------------------------
# Spell checking
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[A-Za-z][a-z]{2,}(?:'[a-z]+)?")
"""Match words ≥3 chars starting with a letter, allowing contractions.
Skips acronyms (all-caps), single/two-letter words, and camelCase fragments."""


def check_file(
    path: Path, spell: SpellChecker
) -> list[tuple[int, set[str]]]:
    """Return a list of (line_number, {misspelled_words}) for a single file."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    prose_lines = extract_prose(text)
    issues: list[tuple[int, set[str]]] = []

    for lineno, line in prose_lines:
        words = WORD_RE.findall(line)
        misspelled = spell.unknown(words)
        if misspelled:
            issues.append((lineno, misspelled))

    return issues


# ---------------------------------------------------------------------------
# Wordlist management
# ---------------------------------------------------------------------------


def load_wordlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        w.strip().lower()
        for w in path.read_text().splitlines()
        if w.strip() and not w.strip().startswith("#")
    ]


def save_wordlist(path: Path, words: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = sorted(set(words))
    path.write_text("\n".join(unique) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Spell check .qmd files in a Quarto project."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Project root directory (default: .)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Check specific files instead of scanning a directory",
    )
    parser.add_argument(
        "--wordlist",
        default="script/wordlist.txt",
        help="Path to custom wordlist (default: script/wordlist.txt)",
    )
    parser.add_argument(
        "--add-unknown",
        action="store_true",
        help="Interactively add unknown words to the wordlist",
    )
    parser.add_argument(
        "--add-all",
        action="store_true",
        help="Add all unknown words to the wordlist without prompting",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show only per-file counts, not individual words",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    wordlist_path = Path(args.wordlist)

    # Set up spell checker
    spell = SpellChecker()
    custom_words = load_wordlist(wordlist_path)
    if custom_words:
        spell.word_frequency.load_words(custom_words)

    # Find .qmd files: explicit list or directory scan
    if args.files:
        qmd_files = [Path(f) for f in args.files if f.endswith(".qmd")]
    else:
        qmd_files = sorted(root.rglob("*.qmd"))

    if not qmd_files:
        print("No .qmd files to check.")
        return 0

    print(f"Checking {len(qmd_files)} .qmd file(s)\n")

    total_issues = 0
    all_unknown: set[str] = set()
    files_with_issues = 0

    for filepath in qmd_files:
        try:
            rel = filepath.relative_to(root)
        except ValueError:
            rel = filepath
        issues = check_file(filepath, spell)

        if not issues:
            continue

        files_with_issues += 1
        file_unknown: set[str] = set()
        for _, words in issues:
            file_unknown |= words

        all_unknown |= file_unknown
        total_issues += len(file_unknown)

        if args.summary:
            print(f"  {rel}: {len(file_unknown)} unknown word(s)")
        else:
            print(f"  {rel}:")
            for lineno, words in issues:
                print(f"    L{lineno}: {', '.join(sorted(words))}")
            print()

    # Summary
    print("-" * 60)
    print(
        f"{total_issues} unique unknown word(s) across "
        f"{files_with_issues}/{len(qmd_files)} file(s)"
    )
    print("")
    print("Fix any typos, or add false positives to script/wordlist.txt.")

    # Bulk add mode
    if args.add_all and all_unknown:
        all_words = custom_words + list(all_unknown)
        save_wordlist(wordlist_path, all_words)
        print(f"\nAdded {len(all_unknown)} word(s) to {wordlist_path}")
        print("Review the wordlist, remove false positives, and re-run.")
        return 0

    # Interactive add mode
    if args.add_unknown and all_unknown:
        print("\nReview unknown words (y = add to wordlist, n = skip, q = quit):\n")
        added: list[str] = []
        for word in sorted(all_unknown):
            suggestions = spell.candidates(word)
            hint = f"  (suggestions: {', '.join(list(suggestions)[:5])})" if suggestions else ""
            try:
                resp = input(f"  '{word}'{hint} [y/n/q]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if resp == "q":
                break
            if resp == "y":
                added.append(word)

        if added:
            all_words = custom_words + added
            save_wordlist(wordlist_path, all_words)
            print(f"\nAdded {len(added)} word(s) to {wordlist_path}")

    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())