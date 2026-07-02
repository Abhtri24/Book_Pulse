"""
BookPulse seed data uploader.

Parses novel entries written in the agreed template format and uploads them
via the existing /auth/register/author, /books, and /books/{id}/snippets
endpoints, all under a single shared "seed curator" account.

Usage:
    python seed_upload.py path/to/novel_block.txt
    python seed_upload.py path/to/batch_file.txt      # supports multiple
                                                        # "### Novel NN" blocks
                                                        # in one file

Expected template per novel (matches what we've been using in chat):

### Novel 01
Title: 
Original Author: 
Source URL: 
Source Platform: (webnovel/royalroad/tapas/wattpad/other)
Synopsis: 
Platform Tags: 
---
Excerpt (Ch1 opening, 200-600 words):

[excerpt text]

---
"""

import sys
import re
import json
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config — adjust to match your local/deployed environment
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"

SEED_AUTHOR_USERNAME = "seed_curator"
SEED_AUTHOR_EMAIL = "seed.curator.bookpulse@gmail.com"
SEED_AUTHOR_PASSWORD = "ChangeMe123!seed"  # local/dev only, not a real account

# Fields recognized as the start of a new labeled field in the template.
FIELD_LABELS = [
    "Title",
    "Original Author",
    "Source URL",
    "Source Platform",
    "Synopsis",
    "Platform Tags",
]

VALID_PLATFORMS = {"royalroad", "tapas", "wattpad", "webnovel", "own_site", "other"}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_novel_blocks(raw_text: str) -> list[dict]:
    """Split a file into one or more novel blocks and parse each."""
    # Split on lines like "### Novel 01" — if there's no such header, treat
    # the whole file as a single block.
    chunks = re.split(r"^###\s*Novel\s*\d+.*$", raw_text, flags=re.MULTILINE)
    chunks = [c for c in chunks if c.strip()]
    if not chunks:
        chunks = [raw_text]
    return [parse_single_block(c) for c in chunks]


def parse_single_block(text: str) -> dict:
    lines = text.splitlines()
    fields: dict[str, str] = {label: "" for label in FIELD_LABELS}
    excerpt_lines: list[str] = []

    current_field = None
    in_excerpt = False
    seen_first_dash_separator = False

    label_pattern = re.compile(
        r"^(" + "|".join(re.escape(l) for l in FIELD_LABELS) + r"):\s*(.*)$"
    )

    for line in lines:
        stripped = line.strip()

        if not in_excerpt:
            label_match = label_pattern.match(line)
            if label_match:
                current_field = label_match.group(1)
                fields[current_field] = label_match.group(2).strip()
                continue

            if stripped == "---":
                seen_first_dash_separator = True
                current_field = None
                continue

            if stripped.lower().startswith("excerpt"):
                in_excerpt = True
                current_field = None
                continue

            if current_field and stripped:
                fields[current_field] = (fields[current_field] + " " + stripped).strip()
            continue

        # inside excerpt block
        if stripped == "---":
            in_excerpt = False
            continue
        excerpt_lines.append(line)

    excerpt = "\n".join(excerpt_lines).strip()

    return {
        "title": fields["Title"].strip(),
        "original_author_name": fields["Original Author"].strip(),
        "external_url": fields["Source URL"].strip(),
        "source_platform": normalize_platform(fields["Source Platform"]),
        "description": fields["Synopsis"].strip(),
        "platform_tags": fields["Platform Tags"].strip(),
        "excerpt": excerpt,
    }


def normalize_platform(raw: str) -> str:
    raw = raw.lower().strip()
    for platform in VALID_PLATFORMS:
        if platform in raw:
            return platform
    return "other"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_entry(entry: dict) -> list[str]:
    problems = []
    if not entry["title"]:
        problems.append("missing Title")
    if not entry["external_url"]:
        problems.append("missing Source URL")
    if not entry["description"]:
        problems.append("missing Synopsis")
    if not entry["excerpt"]:
        problems.append("missing Excerpt")
    else:
        word_count = len(entry["excerpt"].split())
        if word_count < 200 or word_count > 600:
            problems.append(
                f"excerpt word count out of range: {word_count} words "
                f"(needs 200-600)"
            )
    return problems


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def get_seed_author_token() -> str:
    """Register the shared seed author if needed, otherwise log in."""
    register_payload = {
        "username": SEED_AUTHOR_USERNAME,
        "email": SEED_AUTHOR_EMAIL,
        "password": SEED_AUTHOR_PASSWORD,
        "bio": "Seed data curator account for bootstrapping BookPulse discovery.",
    }
    resp = requests.post(f"{BASE_URL}/auth/register/author", json=register_payload)

    if resp.status_code == 201:
        print(f"Registered new seed author account: {SEED_AUTHOR_USERNAME}")
    elif resp.status_code == 409:
        print(f"Seed author account already exists, logging in instead.")
    else:
        print(f"Registration failed with status {resp.status_code}:")
        print(resp.text)
        resp.raise_for_status()

    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": SEED_AUTHOR_EMAIL, "password": SEED_AUTHOR_PASSWORD},
    )
    login_resp.raise_for_status()
    return login_resp.json()["access_token"]


def create_book(token: str, entry: dict) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": entry["title"],
        "description": entry["description"],
        "external_url": entry["external_url"],
        "source_platform": entry["source_platform"],
    }
    resp = requests.post(f"{BASE_URL}/books", json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["id"]


def create_snippet(token: str, book_id: str, content: str, chapter_number: int = 1) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"content": content, "chapter_number": chapter_number}
    resp = requests.post(
        f"{BASE_URL}/books/{book_id}/snippets", json=payload, headers=headers
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: python seed_upload.py path/to/novel_file.txt")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    raw_text = filepath.read_text(encoding="utf-8")
    entries = parse_novel_blocks(raw_text)
    print(f"Parsed {len(entries)} novel entr{'y' if len(entries) == 1 else 'ies'} from {filepath.name}\n")

    # Validate all before uploading anything
    any_invalid = False
    for i, entry in enumerate(entries, start=1):
        problems = validate_entry(entry)
        if problems:
            any_invalid = True
            print(f"[Novel {i}: {entry['title'] or '(untitled)'}] INVALID:")
            for p in problems:
                print(f"  - {p}")
    if any_invalid:
        print("\nFix the issues above and re-run. No uploads were made.")
        sys.exit(1)

    token = get_seed_author_token()

    results = []
    for entry in entries:
        try:
            book_id = create_book(token, entry)
            snippet = create_snippet(token, book_id, entry["excerpt"], chapter_number=1)
            print(
                f"Uploaded '{entry['title']}' "
                f"(book_id={book_id}, snippet_status={snippet.get('processing_status')})"
            )
            if entry["platform_tags"]:
                print(f"  Platform tags (for later classifier comparison): {entry['platform_tags']}")
            results.append({"title": entry["title"], "book_id": book_id, "snippet_id": snippet.get("id")})
        except requests.HTTPError as e:
            print(f"FAILED to upload '{entry['title']}': {e.response.status_code} {e.response.text}")

    print(f"\nDone. {len(results)}/{len(entries)} uploaded successfully.")


if __name__ == "__main__":
    main()