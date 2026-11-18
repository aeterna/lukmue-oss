#!/usr/bin/env python3
"""Fail when a workflow uses an external action without a full commit SHA."""
import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
PINNED = re.compile(r"@[0-9a-f]{40}$")
bad = []
for path in sorted(Path(".github/workflows").glob("*.y*ml")):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = USES.match(line)
        if match and not match[1].startswith("./") and not PINNED.search(match[1]):
            bad.append(f"{path}:{number}: {match[1]}")
if bad:
    print("Actions must be pinned to a full commit SHA:", *bad, sep="\n", file=sys.stderr)
    sys.exit(1)
print("ok: actions are pinned")
