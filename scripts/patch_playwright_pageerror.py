#!/usr/bin/env python3
"""Guard Playwright's unguarded `pageError.location` access.

Playwright 1.60.0's BrowserContext PageError handling reads
`pageError.location.{url,lineNumber,columnNumber}` (two sites in
driver/package/lib/coreBundle.js: the client dispatcher and the
instrumentation path). Firefox - which Camoufox drives - can emit an uncaught
page error with no `location`. The Akamai bot sensor on eBay's /sch/ pages does
exactly this.

Two failure modes have to be closed, and the second is easy to miss:

1. The raw read `pageError.location.url` throws TypeError when location is
   undefined.
2. Even guarded to undefined, the dispatched event is validated against the
   protocol schema, which requires `location.url` to be a *string* and
   line/column to be *numbers*. An undefined there throws
   `ValidationError: location.url: expected string, got undefined`.

Either throw lands inside a Node event-emit handler, is unhandled, and crashes
the entire Playwright driver subprocess. Every later request 502s ("Connection
closed while reading from the driver") until the container is restarted.

Fix: rewrite each field read to optional-chaining plus a correctly-typed
fallback, so a missing location degrades to an empty location object that
passes schema validation instead of killing the process. Fallbacks are no-ops
when location is present, so behavior is unchanged on the normal path.

Run at image-build time, after `pip install` lands Playwright. Idempotent (the
patched form contains none of the raw target substrings). Fails loudly if the
targets are absent, so a future Playwright bump that restructures this code
can't silently ship the crash again.
"""
import pathlib
import sys

import playwright

# Raw read -> guarded read with a type-correct fallback. The fallbacks satisfy
# the protocol validator (url: string, line/column: number) for locationless
# page errors.
REPLACEMENTS = {
    "pageError.location.url": '(pageError.location?.url ?? "")',
    "pageError.location.lineNumber": "(pageError.location?.lineNumber ?? 0)",
    "pageError.location.columnNumber": "(pageError.location?.columnNumber ?? 0)",
}
PATCHED_SENTINEL = 'pageError.location?.url ?? ""'

bundle = pathlib.Path(playwright.__file__).parent / "driver/package/lib/coreBundle.js"
src = bundle.read_text()

applied = 0
for raw, guarded in REPLACEMENTS.items():
    count = src.count(raw)
    if count:
        src = src.replace(raw, guarded)
        applied += count

if applied == 0:
    if PATCHED_SENTINEL in src:
        print("[patch] already applied; nothing to do")
        sys.exit(0)
    sys.exit(
        "[patch] FAILED: no `pageError.location.*` reads found in coreBundle.js. "
        "The Playwright version likely changed - re-verify the page-error crash "
        "fix (eBay /sch/) before shipping."
    )

bundle.write_text(src)
print(f"[patch] guarded {applied} `pageError.location` read(s) in {bundle}")
