# Architectural Decisions

## 001 - Browser driver: Camoufox

**Decision:** Use Camoufox as the initial browser/stealth driver.

**Why Camoufox over Playwright stealth:**
- Fingerprint spoofing happens in native C++ code, not injected JavaScript. Structurally harder to detect.
- Playwright stealth is Chromium-only and fights against Chromium's own design (CDP automation flags, Runtime.Enable leaks). Arms race with the browser vendor.
- Camoufox wraps Playwright's API, so the automation surface is familiar.

**Known risks:**
- Single maintainer (daijro), had a year-long maintenance gap.
- PyPI package lags the repo.
- Self-described as "highly experimental."

**Mitigation:**
- Clean abstraction boundary between Passthrough and the driver layer. The rest of the system doesn't know Camoufox exists.
- If Camoufox dies: fork it, switch to Playwright stealth, or adopt whatever comes next. Swapping the driver is a contained change, not a rewrite.
- No binary patching in our own code unless forced by a dead dependency.

## 002 - Challenge adapter pattern

**Decision:** Detection and solving of challenges are owned by provider-specific adapters, not the core flow.

**Interface:**
```
ChallengeAdapter:
    name         -> "cloudflare" | "datadome" | ...
    detect(page) -> clear | challenged | blocked
    solve(page)  -> success | failure
```

**Why:** Each protection provider has completely different challenge pages, detection signals, and solve strategies. Coupling these to the core flow means every new provider (or provider change) touches core code.

**How it works:** The core flow runs registered adapters in order. First adapter whose `detect()` returns `challenged` owns the solve cycle. If none claim it, the page is treated as clear.

**Symmetry with the driver abstraction:** The driver (Camoufox) is abstracted behind an interface so it can be swapped. The challenge layer (Cloudflare) is abstracted behind an interface so it can be swapped. The core flow knows neither.

## 003 - No binary patching

**Decision:** Passthrough does not patch browser binaries. Stealth is delegated to the driver.

**Why:** Binary patching creates a maintenance treadmill tied to upstream browser releases. This is the failure mode that killed FlareSolverr. Owning the fork doesn't make the treadmill slower.

**Escape hatch:** If the driver dies, forking it and maintaining patches is a contingency, not the architecture.
