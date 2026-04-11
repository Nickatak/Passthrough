# Implementation Slices

Ordered list of buildable increments. Each slice produces something testable.

## 1a - Scaffolding + interfaces

- `pyproject.toml` (dependencies, project metadata)
- Package structure (`__init__.py` files)
- `drivers/base.py` - driver interface
- `adapters/base.py` - adapter interface
- End state: installable package, contracts defined, nothing runs yet

## 1b - Pipeline

- `pipeline.py` - the 7-step orchestration working against the interfaces
- End state: core logic exists, no way to call it yet

## 1c - API + wiring

- `api.py` - endpoint, request/response models
- `main.py` - composition root with a stub driver (returns canned HTML)
- End state: `curl` it, get a response back. Full loop works.

## 2 - Camoufox driver

- `drivers/camoufox.py` - real browser navigation, page content extraction, cookie/header capture
- Swap the stub for Camoufox in `main.py`
- End state: hit a real URL, get back real content (no challenge handling)

## 3 - Cloudflare adapter

- `adapters/cloudflare.py` - detection logic (status code, headers, title, DOM)
- Solve strategies (JS challenge wait, Turnstile click)
- Wire into the pipeline
- End state: navigate through Cloudflare challenges

## 4 - Hardening

- Timeout enforcement, error classification, cleanup on failure
- Error codes from the flow doc (`invalid_request`, `navigation_failed`, `challenge_blocked`, `solve_failed`, `capture_failed`)
- End state: robust error handling across all failure modes
