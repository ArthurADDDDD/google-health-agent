"""Fail closed on common secret and personal-data artifacts before publication."""

from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATH_PARTS = {"data", "raw", "reports", "credentials", "secrets"}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".mako",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Google access token": re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}"),
    "Google refresh token": re.compile(r"\b1//[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}"),
    "generic API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "personal path": re.compile("/" + r"Users/[^/\s]+/"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE),
}
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item.decode()) for item in result.stdout.split(b"\0") if item]


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    if any(part in FORBIDDEN_PATH_PARTS for part in path.parts):
        findings.append("tracked private-data directory")
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return findings
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        findings.append("unexpected binary tracked file")
        return findings
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if name == "email" and match.group(1).lower() == "example.com":
                continue
            findings.append(f"{name} at character {match.start()}")
    for match in IP_PATTERN.finditer(text):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if address.is_loopback or address.is_unspecified:
            continue
        findings.append(f"non-demo IPv4 address at character {match.start()}")
    return findings


def main() -> int:
    findings = {str(path): issues for path in tracked_files() if (issues := scan_file(path))}
    if findings:
        print("Secret/privacy scan failed:", file=sys.stderr)
        for path, issues in findings.items():
            for issue in issues:
                print(f"- {path}: {issue}", file=sys.stderr)
        return 1
    print("Secret/privacy scan passed for all tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
