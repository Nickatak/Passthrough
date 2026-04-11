# Passthrough

A headless browser service that navigates Cloudflare and similar browser challenges on behalf of callers, returning usable cookies and page content via HTTP API.

## Why

FlareSolverr served this role for years but is now effectively unmaintained. Its approach - patching the Chromium binary to avoid detection - is fragile and breaks whenever the browser or the protection layer updates. When Indeed started returning 500s, it was the final nudge.

Byparr exists as a drop-in FlareSolverr replacement, but Passthrough isn't interested in preserving that API contract. This is a clean-sheet design that does the same job with a better foundation.

## Principles

- **No binary patching.** Stealth is handled at a higher abstraction level - browser automation libraries and configuration, not hex-editing executables.
- **Own API spec.** Designed for clarity and our actual use cases, not backwards compatibility with FlareSolverr consumers.
- **Modern tooling.** Built on actively maintained libraries with real communities behind them.

## How it works

See [docs/flow.md](docs/flow.md) for the full request lifecycle.

## Status

Early design. Requirements and implementation approach TBD.
