# Contributing

## Principles

### Explicit before implicit

No magic. If behavior depends on configuration, registration order, naming conventions, or decorator side effects - make it visible at the call site. A reader should be able to trace what happens by reading the code, not by knowing framework internals.

### Readability over everything

Code is read far more than it's written. When there's a tension between conciseness and clarity, clarity wins. When there's a tension between cleverness and obviousness, obviousness wins.

This doesn't mean verbose - it means clear. A well-named function with a straightforward body beats a compact one that requires mental unpacking.

### Comments explain "why", not "what"

The code itself communicates what it does. Comments exist for:

- **Decisions** - why this approach over the alternatives
- **Constraints** - why something looks odd (external API quirks, library limitations)
- **Non-obvious reasoning** - anything where the motivation isn't self-evident from the code

If a block of code needs a "what" comment to be understandable, rewrite the code.

### Respect the abstractions

The architecture has deliberate boundaries - driver interface, adapter interface, composition root. These exist for real reasons (documented in [docs/decisions.md](docs/decisions.md)).

Don't add new abstractions without a concrete reason. Don't bypass existing ones for convenience. If an abstraction is wrong, change it - don't work around it.

### Keep it flat

Within each layer, prefer straightforward linear code over nested indirection. Don't introduce helpers, base classes, or wrapper layers until the complexity genuinely demands it. Three similar lines are better than a premature abstraction.
