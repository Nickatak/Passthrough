#!/usr/bin/env python3
"""Guard Playwright's unguarded `pageError.location` access.

Playwright 1.60.0's BrowserContext PageError handling reads
`pageError.location.{url,lineNumber,columnNumber}` with no null guard (two
sites in driver/package/lib/coreBundle.js: the client dispatcher and the
instrumentation path). Firefox - which Camoufox drives - can emit an uncaught
page error with no `location`. The Akamai bot sensor on eBay's /sch/ pages does
exactly this. The unguarded read then throws a TypeError inside a Node
event-emit handler; that throw is unhandled and crashes the entire Playwright
driver subprocess. Every later request 502s ("Connection closed while reading
from the driver") until the container is restarted.

Fix: rewrite `pageError.location.` -> `pageError.location?.` so a missing
location degrades to undefined fields instead of killing the process. Optional
chaining is a no-op when location is present, so behavior is unchanged on the
normal path.

Run at image-build time, after `pip install` lands Playwright. Idempotent
(already-guarded reads contain no `pageError.location.` substring). Fails loudly
if the target pattern is absent, so a future Playwright bump that restructures
this code can't silently ship the crash again.
"""
import pathlib
import sys

import playwright

UNGUARDED = "pageError.location."
GUARDED = "pageError.location?."

bundle = pathlib.Path(playwright.__file__).parent / "driver/package/lib/coreBundle.js"
src = bundle.read_text()

unguarded = src.count(UNGUARDED)
already = src.count(GUARDED)

if unguarded == 0:
    if already > 0:
        print(f"[patch] already applied ({already} guarded reads); nothing to do")
        sys.exit(0)
    sys.exit(
        "[patch] FAILED: no `pageError.location.` reads found in coreBundle.js. "
        "The Playwright version likely changed - re-verify the page-error crash "
        "fix (eBay /sch/) before shipping."
    )

bundle.write_text(src.replace(UNGUARDED, GUARDED))
print(f"[patch] guarded {unguarded} `pageError.location` read(s) in {bundle}")
