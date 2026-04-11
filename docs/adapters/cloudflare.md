# Cloudflare Adapter

## Detection signals

Cloudflare challenges come in a few forms, detectable by different signals.

### JS Challenge (managed challenge)

The "Checking your browser..." spinner.

- Page title is "Just a moment..."
- Body contains a `#challenge-running` or `#challenge-form` element
- `cf-mitigated` response header present
- HTTP status 403

### Turnstile (interactive challenge)

The checkbox/widget.

- An iframe with `src` containing `challenges.cloudflare.com/turnstile`
- A `div` with `class="cf-turnstile"` or `data-sitekey` attribute

### Block page (no solve path)

Cloudflare decided you're a bot and isn't offering a challenge.

- Page contains "Access denied" or "Sorry, you have been blocked"
- HTTP status 403 with no challenge elements
- `cf-chl-bypass` header absent

## Detection order

Check cheapest signals first:

1. **Status code** - if 200, not a Cloudflare challenge.
2. **Response headers** - `cf-mitigated`, `cf-chl-bypass`.
3. **Page title** - "Just a moment..." is the JS challenge signature.
4. **DOM inspection** - challenge-specific elements, only if earlier signals are ambiguous.

## Solve strategies

### JS Challenge

Typically self-solving. Cloudflare runs JS environment checks and, if the browser passes, auto-redirects. The solve strategy is: wait for navigation to complete (the challenge page redirects to the real page).

Wait condition: watch for the URL or page title to change, with a timeout.

### Turnstile

May require clicking the checkbox widget. Locate the Turnstile iframe, click the challenge element within it, then wait for redirect.

### Block page

No solve path. Return `blocked` immediately.

## Notes

These signatures are point-in-time. Cloudflare changes their challenge pages. This adapter will need periodic updates as detection signals evolve.
