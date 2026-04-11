# Passthrough - Request Flow

## Overview

1. **Receive** - Caller sends URL and parameters to the API.
2. **Prepare** - Anti-fingerprinting/stealth config applied to the browser context.
3. **Navigate** - Browser goes to the target URL. This is the request.
4. **Detect** - Check whether Cloudflare (or similar) intercepted with a challenge page.
5. **Solve** - If challenged, resolve it. The browser gets redirected to the real page automatically (Cloudflare sets `cf_clearance` cookies and lets you through).
6. **Capture** - Grab the final page content, cookies, and headers from the now-loaded real page.
7. **Return** - Send it all back to the caller.

## Step details

### 1. Receive

Caller sends a POST to `/request` with a URL and method. We validate the input (is the URL well-formed, is the method supported) and reject bad requests before touching a browser.

This is the cheapest place to fail - no browser resources allocated yet.

### 2. Prepare

Anti-fingerprinting operates at two layers: browser-level and network-level. Camoufox handles the browser layer (canvas, WebGL, fonts, navigator properties, etc. - see [Camoufox stealth docs](https://camoufox.com/stealth/) for details). Everything below is what Passthrough is responsible for.

#### 2a. TLS Fingerprinting (JA3/JA4)

The TLS handshake has a signature - cipher suites offered, extensions, their ordering. Anti-bot systems fingerprint this *before any page content loads*. A real Firefox produces a different TLS fingerprint than a bot using default Python/Node TLS settings.

Since Camoufox is actual Firefox, its TLS fingerprint should be legitimate Firefox. **Verify this assumption** - if we put a proxy between Camoufox and the target, the proxy's TLS stack may replace the fingerprint with its own.

**Status:** Likely handled by Camoufox natively, but needs validation. Becomes our problem if we introduce a proxy layer.

#### 2b. HTTP/2 Fingerprinting

Similar to TLS - the HTTP/2 SETTINGS frames, header ordering, and priority signaling differ between real browsers and automation tools. Anti-bot systems use this as a secondary signal.

Same caveat as TLS: a proxy in the middle can alter this.

**Status:** Likely handled by Camoufox natively, same proxy caveat.

#### 2c. IP Reputation

Cloudflare weighs IP reputation heavily. Datacenter IPs are inherently suspicious. Residential IPs are trusted more. This is outside the browser entirely.

For MVP, we run without a proxy and use whatever IP the host has. If detection rates are high, residential proxy support is the first thing to add.

**Status:** Deferred. MVP runs on host IP.

#### 2d. Behavioral Analysis

Mouse movement patterns, scroll timing, click cadence, how long you "read" a page before interacting. Real humans are messy and variable; bots are precise and consistent.

Cloudflare's lighter challenges (JS challenges) don't require this - they just verify the browser environment. Turnstile and interactive challenges do look at behavior.

**Status:** Deferred. Only needed if we hit interactive challenges that JS solve alone can't clear.

### 3. Navigate

Browser navigates to the target URL. This is a `page.goto(url)` call through Camoufox's Playwright wrapper.

#### What actually happens

The browser sends the HTTP request, follows any redirect chain, and waits for the page to reach a loaded state. If Cloudflare intercepts, the "page" that loads is the challenge page, not the target - that's what Step 4 detects.

#### Timeout strategy

We need a timeout on navigation. Too short and legitimate slow pages fail. Too long and stuck requests hold a browser instance hostage.

Reasonable default: **30 seconds** for initial navigation. This is the Playwright default and covers most real-world page loads. Configurable per-request later if needed.

#### Wait condition

Playwright offers several "wait until" strategies:
- `domcontentloaded` - HTML parsed, not all resources loaded. Fast but may be too early.
- `load` - all resources (images, scripts, stylesheets) finished. What a real user would see.
- `networkidle` - no new network requests for 500ms. Most conservative, catches SPAs that load data after `load`.

For our purposes: **`domcontentloaded`** for the initial navigation. We don't need images and stylesheets to finish - we need to know whether we got the real page or a challenge page. If we got challenged, waiting for `load` on the challenge page wastes time.

After solving (Step 5), we wait for the real page with a more patient strategy.

#### Error cases

- **DNS failure** - target doesn't resolve. Fail fast, return error.
- **Connection refused** - target is down. Fail fast, return error.
- **Timeout** - page didn't load in time. Return error with context.
- **SSL error** - bad cert, expired, etc. Return error. Don't silently bypass.

### 4. Detect

After navigation completes, determine whether we landed on the real page or a challenge page. This is delegated to challenge adapters (see [Decision 002](decisions.md#002---challenge-adapter-pattern)).

The core flow iterates through registered adapters and calls `detect(page)`. Each adapter inspects the page for signals specific to its provider. First adapter to claim the page owns it.

Detection produces one of three states:
- **clear** - no adapter claimed the page. It's the real content. Skip to Capture (Step 6).
- **challenged** - an adapter recognized a solvable challenge. Proceed to Solve (Step 5).
- **blocked** - an adapter recognized its provider but there's no solve path (hard block). Return error to caller.

See [adapters/](adapters/) for provider-specific detection signals and solve strategies.

### 5. Solve

The adapter that claimed the page in Step 4 runs its `solve(page)` method. What this looks like depends entirely on the provider - the core flow doesn't know or care.

After solve completes, the browser should be on the real page (the protection layer redirects automatically after granting clearance). If solve fails (timeout, unsupported challenge type), return error to caller.

### 6. Capture

At this point the browser is on the real page - either because there was no challenge (Step 4 returned clear) or because the adapter solved it (Step 5).

#### Wait for the page to settle

After a challenge solve, the page may still be loading. Switch to a more patient wait strategy here: **`load`** or **`networkidle`**, since we now want the full page content the caller is asking for.

Timeout: same 30s default from Step 3. If the real page can't load in 30s, something else is wrong.

#### Extract

- **Status code** - from the final response, not the challenge page.
- **Headers** - response headers from the final page.
- **Cookies** - all cookies accumulated during the entire navigation chain (including `cf_clearance` and any session cookies set by the target). Full cookie objects: name, value, domain, path, expires, httpOnly, secure.
- **Body** - the page HTML as a string (`page.content()`).

### 7. Return

Package the captured data into the response format defined in the [API spec](api.md) and send it back to the caller.

If any step prior to this failed, return a structured error instead:

```json
{
  "error": "error_code",
  "message": "Human-readable description of what went wrong"
}
```

Error codes map to the step that failed:
- `invalid_request` - Step 1 (bad input)
- `navigation_failed` - Step 3 (DNS, connection, SSL, timeout)
- `challenge_blocked` - Step 4 (hard block, no solve path)
- `solve_failed` - Step 5 (challenge detected but couldn't be solved)
- `capture_failed` - Step 6 (page loaded but extraction failed)
