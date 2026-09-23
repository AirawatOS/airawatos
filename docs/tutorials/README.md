# Writing a tutorial (contributor note)

This folder holds the developer-portal **tutorials** — full, use-case-driven walkthroughs, one Markdown file per
tutorial, rendered at `/developer/tutorials/<slug>/`. To publish a new one: drop a `.md` here and add one tuple
to the `TUTORIALS` registry in `platform-spec/reference/tools/build_portal.py`
(`slug, title, tutorials/<file>.md, blurb, category`), then rebuild the portal.

## Categories

Every tutorial belongs to a **use-case category** (the `CATEGORIES` list in the builder). Current set:

- **Service Delivery** — citizen-facing services (file a complaint, apply for a certificate/licence).
- **Decision Support** — sense → analyse → recommend → a human decides.
- **Cross-Agency Coordination** — federation across tenants/jurisdictions (verify a person, share across agencies).

Add a category to `CATEGORIES` when a genuinely new kind of use case arrives — not per tutorial.

## The shape — every tutorial, in this order

1. **The use case** — the real civic scenario, in plain language.
2. **The challenges** — the hard parts named up front (trust across agencies · consent for personal data ·
   tamper-proof audit · no shared database · works offline · don't rebuild the plumbing · …).
3. **Build it** — the full ordered arc, proven: typically **build → publish → install → run**.
4. **Challenges revisited** — return to each challenge from step 2 and show exactly how the platform met it.
5. **Where this is reference-grade** — honest current limits + links to the relevant Deep Dives.

The challenges bookend (2 ↔ 4) is what makes a tutorial land: it frames the problem a decision-maker cares about,
then proves the platform solved it.

## The one rule

**Every step is a real, proven call.** No invented endpoints, no aspirational request bodies. Before publishing,
run the flow against the live stack (local `:8099` or EC2) and confirm each call returns what the tutorial says.
If part of the flow isn't built yet, either leave it out or move the piece to a Deep Dive — do not fake it. Call
out reference-grade stubs honestly in step 5. (This mirrors the platform-wide no-synthetic-data rule.)

### The drift gate catches the mechanical half

A build-time check — `reference/tools/docs_lint.py` — reads the code's sources of truth and flags docs that
reference something that doesn't exist: a phantom `/bridge/<verb>`, a wrong `x-kind` value, a leaked internal
ADR number, an `/apps/<slug>/` that isn't a real app. It runs automatically at the end of every portal build
(warn-first), or on its own:

```bash
python3 reference/tools/docs_lint.py            # report drift, exit 0 (warn-first)
python3 reference/tools/docs_lint.py --strict   # exit 1 on any finding (CI gate once clean)
```

It only catches the *mechanical* class — a name that doesn't resolve. It cannot judge whether a sentence
*overstates* what the platform does ("no socket", "short-lived token"); that stays with the author and review.
So the gate is a floor, not a substitute for the one rule above.

## House style

- **App-first, API underneath.** Lead every step with what the developer/agency actually does *in an app* —
  **Studio**, **Service Studio**, the **Admin** app, **Network Admin**, the **Marketplace**, **Jan Seva**,
  **Tasks** — using the real on-screen labels (e.g. Service Studio → `＋ New Service`; Marketplace → `Install`).
  Then add a short *"Under the hood → `POST /bridge/…`"* line for the API-minded. The reader should be able to
  finish the tutorial without ever opening a terminal. Use the verbatim button/tab text from the app's
  `dist/index.html`; if a step has **no UI yet**, say so and mark it *API-only today*.
- Put a **reference note** near the top listing the apps used (open at `/apps/<name>/` or install from the
  Marketplace) and use `$VARS` for tenant ids so the reader substitutes their own.
- The `/bridge/*` verb is the "under the hood" detail — never the primary instruction (unless the tutorial is
  specifically about the lower layer).
- Show **expected responses** as fenced `jsonc` with brief `// comments` on the fields that matter.
- **No internal ADR numbers** in the prose — name the feature in plain language and link to the Deep Dive.
- Link out for concepts; don't re-explain them — that's what Deep Dives are for.
