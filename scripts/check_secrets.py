"""Lightweight secret and personal-data scan over tracked files (used locally and in CI).

Fails on likely credentials, private keys, committed .env files and generated datasets.
"""

from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "Anthropic/OpenAI key": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{32,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "assigned secret": re.compile(r"(?i)\b(?:secret_key|api_key|password|token)\s*[:=]\s*['\"][A-Za-z0-9/+_=-]{24,}['\"]"),
}
FORBIDDEN_PATHS = (
    re.compile(r"(^|/)\.env$"),
    re.compile(r"^data/synthetic/(?!README\.md$)"),
    re.compile(r"\.(db|sqlite3?|pem|key)$"),
)
SKIP = (".ipynb", "package-lock.json", ".png", ".svg")


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files"],  # noqa: S607 - developer/CI tool
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    problems = []
    for f in files:
        if any(p.search(f) for p in FORBIDDEN_PATHS):
            problems.append(f"{f}: file type must not be committed")
            continue
        if f.endswith(SKIP) or f == "scripts/check_secrets.py":
            continue
        try:
            text = open(f, encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for name, pat in PATTERNS.items():
            if pat.search(text):
                problems.append(f"{f}: possible {name}")
    for p in problems:
        print("SECRET-SCAN:", p)
    print(f"scanned {len(files)} tracked files; {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
