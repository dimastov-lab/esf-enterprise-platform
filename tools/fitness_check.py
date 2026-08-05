#!/usr/bin/env python3
"""AIOS Core boundary fitness check.

Verifies that a product repository does not import AIOS Core private modules
directly. Products must attach to AIOS only through the public aios_sdk package,
the versioned HTTP API, or published events (ADR-0015 Decision 3).

Usage:
    python fitness_check.py <repo_root>

Exit codes:
    0  — no violations found
    1  — one or more violations found (details printed to stdout)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


_ALLOWED_PREFIXES = ("aios_sdk",)
_BANNED_PREFIXES = ("aios.",)
_BANNED_EXACT = ("aios",)


def _is_banned(name: str) -> bool:
    if name in _BANNED_EXACT:
        return True
    return any(name.startswith(p) for p in _BANNED_PREFIXES)


def _is_allowed(name: str) -> bool:
    return any(name.startswith(p) for p in _ALLOWED_PREFIXES)


def _check_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line, description) for each violation in path."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []

    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if _is_banned(name) and not _is_allowed(name):
                    violations.append(
                        (node.lineno, f"import {name}")
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_banned(module) and not _is_allowed(module):
                violations.append(
                    (node.lineno, f"from {module} import ...")
                )
    return violations


def run(root: Path) -> int:
    py_files = sorted(root.rglob("*.py"))
    total: list[tuple[Path, int, str]] = []

    for path in py_files:
        for lineno, desc in _check_file(path):
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            total.append((rel, lineno, desc))

    if total:
        print("AIOS boundary violation(s) found:")
        for rel, lineno, desc in total:
            print(f"  {rel}:{lineno}: {desc}")
        print(
            "\nProducts must not import AIOS Core private modules. "
            "Use aios_sdk or the HTTP API instead (ADR-0015 Decision 3)."
        )
        return 1

    print(f"OK: no AIOS Core private imports found in {len(py_files)} files.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <repo_root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(Path(sys.argv[1])))
