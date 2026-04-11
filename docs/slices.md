# Implementation Slices

Ordered list of buildable increments. Each slice produces something testable.

## ~~1a - Scaffolding + interfaces~~ done

- `pyproject.toml` (dependencies, project metadata)
- Package structure (`__init__.py` files)
- `drivers/base.py` - driver interface
- `adapters/base.py` - adapter interface
- End state: installable package, contracts defined, nothing runs yet

## ~~1b - Pipeline~~ done

- `pipeline.py` - the 7-step orchestration working against the interfaces
- `errors.py` - shared error vocabulary (pipeline raises, API translates)
- End state: core logic exists, no way to call it yet

## ~~1c - API + wiring~~ done

- `api.py` - endpoint, request/response models
- `main.py` - composition root with a stub driver (returns canned HTML)
- End state: `curl` it, get a response back. Full loop works.

## ~~2a - Browser lifecycle~~ done

- `CamoufoxDriver.start()` and `stop()` - launch/kill the browser
- End state: Firefox starts, shuts down cleanly

## ~~2b - Navigation~~ done

- `new_page()`, `close_page()`, `goto()`
- End state: can visit a real URL, page object is usable

## ~~2c - Capture~~ done

- `capture(page)` - extract status, headers, cookies, body
- `goto()` stashes the Response in `self._responses: dict[Page, Response]`
- `capture()` reads from it, `close_page()` cleans up the entry
- End state: full page data extraction works

## ~~2d - Integration~~ done

- Swap StubDriver for CamoufoxDriver in `main.py`
- End state: curl a real URL end-to-end, get back real content (no challenge handling)

## ~~3 - Cloudflare adapter~~ done

- `adapters/cloudflare.py` - detection via page title and DOM inspection
- JS challenge solve: wait for title change (auto-solves via Camoufox stealth)
- Turnstile solve: click checkbox in cross-origin iframe (humanize + disable_coop)
- Pipeline post-solve reload for clean Response capture
- CamoufoxDriver: enabled humanize, disable_coop, i_know_what_im_doing
- End state: navigate through Cloudflare challenges

## 4 - Hardening

- [ ] Timeout enforcement, error classification, cleanup on failure
- [ ] Error codes from the flow doc (`invalid_request`, `navigation_failed`, `challenge_blocked`, `solve_failed`, `capture_failed`)
- End state: robust error handling across all failure modes
