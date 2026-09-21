# Quickstart — your first solution (Hello World)

*Build, publish, and install a tiny working solution on AirawatOS in about ten minutes — first the fast, AI-assisted way, then the same thing by hand so you can see every moving part.*

Everything here happens in the browser. You don't install a toolchain, and you don't touch the servers — you build inside **Studio** (the platform's own build workspace) and the platform certifies, delivers, and runs your work for you.

## Before you start

- **Sign in as a developer.** You need a developer login with its own **sandbox tenant** — a safe, walled-off workspace with test data, where nothing you do affects a real deployment. If you don't have one, ask your operator to provision a developer participant for you.
- **Know the shape of the goal.** A **component** is one building block (a driver, an engine, an app). A **solution** bundles components into something installable in one click. "Hello World" is the smallest possible version: one component, published and installed as a one-member solution.

That's the whole mental model. Now let's build it.

---

## The fast path — with the AI copilot

Studio has a built-in AI assistant, the **Solution Expert**, that helps you go from a sentence to working, certified components.

1. **Open Studio** and create a **New Project** (pick it from the project dropdown, top-left). A project is your build workspace — it holds the components you're working on before they're published.

2. **Open the Solution Expert** (the 🧠 panel on the right) and describe what you want in plain words — for example:

   > *"A simple app that greets the signed-in user and shows which tenant they're in."*

   The assistant proposes a small set of components for your goal and can **scaffold** them into your project — each with a valid `meta.yaml` and a runnable starting point.

3. **Generate the code.** Open a scaffolded component and use **✨ Generate with AI** (or keep chatting with the Solution Expert). It drafts the code from your description. Read what it wrote — you're always in control; the AI drafts, you decide.

4. **Test it (safety gate 1).** Run the component in the sandbox: **Test** for a driver/engine, or **Preview** for an app. It must produce a passing run before it can be published — broken code stops here.

5. **Publish it (safety gate 2).** **Publish** certifies the component — checks it conforms and signs it — and lists it in the Marketplace. A component that hasn't passed a test can't be published.

6. **Compose a solution.** Once your component is published, **Compose** the project into a **solution** — a one-click bundle. (Yours has a single member for now; real solutions bundle several.)

7. **Install it.** Open the **Marketplace**, find your solution, and **Install** it into your tenant. Installing fans out and sets everything up.

8. **See it live.** Open your app from the desktop (or, for a driver, check that it wrote its data in the **Data** browser). That's a working solution you built, certified, and installed — end to end.

You just used the full lifecycle: **describe → generate → test → publish → compose → install**. Everything you built is signed, sandboxed, and traceable, without you wiring any of that up.

---

## The same thing by hand

The AI path did a few things for you. Here's what actually happened underneath — do it yourself once and the platform stops feeling like magic.

### 1 · Add a component

In your project's explorer, **right-click a layer → ＋ New** and pick a kind (`app` for our greeter). Studio **scaffolds** it: a folder with a `meta.yaml` and a starting entrypoint.

### 2 · Fill in the description file (`meta.yaml`)

`meta.yaml` *is* your component's contract — its identity and everything it's allowed to touch. A minimal app:

```
component_id: ds:<your-developer-id>:app/hello-world   # its unique, resolvable name
kind: app
version: 0.1.0
entrypoint: index.html      # apps ship a web page; the bundle lives under dist/
reads:  []                  # this greeter needs no governed data
writes: []                  # …and writes none
```

The rules you declare here are the *complete* list of what your component can do. A driver or engine would add `reads` / `writes` (the data types it may touch), `egress` (outside websites it may call), and `secrets` (keys, delivered only at use). See [What your code can touch](/developer/build/capabilities/) and [Anatomy of a component](/developer/build/anatomy/).

### 3 · Write the code

For our app, edit `dist/index.html` — a plain page. It reads the platform-provided config (which tells it the signed-in user's tenant) and says hello:

```
<!doctype html><meta charset=utf-8>
<h1 id=greeting>Hello…</h1>
<script>
  fetch('config.json').then(r=>r.json()).then(c=>{
    document.getElementById('greeting').textContent = 'Hello — you are in tenant ' + (c.tenant || 'unknown');
  });
</script>
```

An **app holds no authority of its own** — it acts as the signed-in user and reaches data only through the platform, never a side channel. A **driver** or **engine** instead has a `run.py` with a small, declared surface: a driver's `main()` runs to completion; an engine exposes a table of named actions (verbs). Both do all their I/O through the **broker** — the single guarded door described in [Zero-Trust Architecture](/developer/deep-dives/zero-trust/).

### 4 · Test, publish, compose, install

The rest is the same as the fast path, just done by clicking rather than chatting:

- **Test / Preview** — run it in the sandbox (gate 1).
- **Publish** — certify + sign + list in the Marketplace (gate 2).
- **Compose** — bundle the project into a solution.
- **Install** — from the Marketplace, into your tenant.

Open it, and you've hand-built your first solution.

---

## What you just learned

- A **solution** is a bundle of **components**; you build components in **Studio** and install them from the **Marketplace**.
- Every component **declares what it may touch** in `meta.yaml`, and nothing else is reachable — trust rests on the certificate and the host, not your code.
- Two gates protect every release: it must **test green**, then it's **certified and signed** before it can be published or run.
- The AI copilot is a shortcut through that same governed path — never a bypass of it.

## Where to go next

- **[What is a component?](/developer/build/what-is-a-component/)** and **[Anatomy of a component](/developer/build/anatomy/)** — the building block, in detail.
- **[Working with governed data](/developer/build/governed-data/)** — how a driver or engine reads and writes the shared record book.
- **[Build, test, publish](/developer/build/lifecycle/)** — the lifecycle and its two gates, spelled out.
- **[Deep Dives](/developer/deep-dives/)** — the concepts underneath: zero-trust, the shared vocabulary, components, runtimes, interaction, and more.
