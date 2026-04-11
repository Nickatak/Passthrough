# Project Structure

```
passthrough/
├── docs/
├── passthrough/
│   ├── __init__.py
│   ├── main.py
│   ├── api.py
│   ├── pipeline.py
│   ├── drivers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── camoufox.py
│   └── adapters/
│       ├── __init__.py
│       ├── base.py
│       └── cloudflare.py
├── pyproject.toml
└── README.md
```

## Components

### main.py - Entry point

Assembles the application. Creates the FastAPI app, instantiates the driver and adapters, wires them into the pipeline, and registers API routes.

This is the only place where concrete implementations (Camoufox, Cloudflare) are referenced by name. Everything else works through interfaces.

### api.py - HTTP layer

Defines the API endpoints and request/response models. Receives incoming requests, hands them to the pipeline, and returns the result.

Owns: input validation, response serialization, HTTP error codes.
Does not own: browser logic, challenge detection, or anything about how a request is fulfilled.

### pipeline.py - Core orchestration

The 7-step flow (Receive -> Prepare -> Navigate -> Detect -> Solve -> Capture -> Return). Coordinates the driver and adapters to process a request end-to-end.

Owns: sequencing, timeout enforcement, error classification.
Does not own: how the browser works or how challenges are identified/solved. Talks to both through interfaces only.

### drivers/base.py - Driver interface

Defines what Passthrough needs from a browser driver: create a context, navigate to a URL, extract page content/cookies/headers, and clean up.

No implementation here. Just the contract.

### drivers/camoufox.py - Camoufox driver

Implements the driver interface using Camoufox. Handles browser lifecycle, fingerprint profile configuration, and Playwright API calls.

This is the only file that imports camoufox.

### adapters/base.py - Challenge adapter interface

Defines what Passthrough needs from a challenge adapter: detect whether a page is challenged, and solve it if so.

No implementation here. Just the contract.

### adapters/cloudflare.py - Cloudflare adapter

Implements the adapter interface for Cloudflare challenges. Owns all Cloudflare-specific detection signals and solve strategies.

See [adapters/cloudflare.md](adapters/cloudflare.md) for the detection/solve details.

## Dependency rules

Arrows point inward. Outer layers depend on inner layers, never the reverse.

```
api.py -> pipeline.py -> drivers/base.py
                      -> adapters/base.py

main.py -> everything (wiring only)
```

- `api.py` imports `pipeline.py`. Never imports drivers or adapters.
- `pipeline.py` imports `drivers/base.py` and `adapters/base.py`. Never imports concrete implementations.
- `main.py` imports concrete implementations to wire them together. This is the composition root.
- `camoufox.py` and `cloudflare.py` import their respective `base.py` and external libraries. Nothing else in the project imports them directly.
