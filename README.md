# Site Cloner Agent

A conversational CLI agent — built in the spirit of **Cursor** / **Windsurf** / **Claude Code** — that clones any website you point it at. It reasons in a ReAct loop, calls real tools (HTTP fetch, headless Chromium screenshots, vision, file I/O), validates its own output, and remembers what it learns across runs.

Powered by **Gemini 2.5 Pro** (reasoning) and **Gemini 2.5 Flash** (vision + memory summarization).

```
┌─ Site Cloner ────────────────────── gemini-2.5-pro ─┐
│  ▸ welcome — type a URL to clone.                   │
│  you  ▸  clone https://scaler.com                   │
│  ·  Plan: fetch reference, screenshot, see, draft.  │
│  ▸ tool  fetch_url(url=https://scaler.com)          │
│    ✓ {ok:true, title:"Scaler — Master Tech…", …}    │
│  ▸ tool  screenshot_url(url=…, path=_ref/source.png)│
│    ✓ {ok:true, bytes:184320, viewport:1440x900}     │
│  ▸ tool  look_at(path=_ref/source.png)              │
│    ✓ {ok:true, observations:"Dark navy hero…"}      │
│  ▸ tool  write_file(path=index.html)   ✓            │
│  ◇ validator: index.html OK — header, hero, footer  │
│  ▸ tool  screenshot_url(url=index.html, …)  ✓       │
│  ▸ tool  look_at(path=_ref/mine.png)        ✓       │
│  ·  Hero gradient drifted; tightening colors.       │
│  ▸ tool  write_file(path=styles.css)        ✓       │
│  ▸ tool  open_in_browser(path=index.html)   ✓       │
│  agent ▸ done — opened output/2026…/index.html      │
│  ☷ memory: +2 patches                               │
│ ●  weaving…                                         │
│ ╭─ message ─────────────────────────────────────────╮│
│ │ ▸ _                                               ││
│ ╰───────────────────────────────────────────────────╯│
│ site-cloner · gemini-2.5-pro  step 14 · tools 6    │
└─────────────────────────────────────────────────────┘
```

---

## Table of contents
1. [What it does](#what-it-does)
2. [Design philosophy](#design-philosophy)
3. [Architecture](#architecture)
4. [The agent loop in detail](#the-agent-loop-in-detail)
5. [Long-term memory — `MEMORY.md`](#long-term-memory--memorymd)
6. [Code walkthrough](#code-walkthrough)
7. [Setup](#setup)
8. [Running it](#running-it)
9. [Testing](#testing)
10. [Demo recipe](#demo-recipe)

---

## What it does

You type `clone https://stripe.com` (or just `stripe.com`). The agent:

1. **Fetches** the page (HTTP) and extracts a structured summary — title, description, section outline, dominant colors, cleaned text — without dumping raw HTML into its context.
2. **Screenshots** the page with **headless Chromium** (Playwright) and saves a PNG.
3. **Looks at** that PNG with **Gemini Vision** and gets back free-form observations — palette, header layout, hero composition, sections, footer, typography vibe.
4. **Drafts** `index.html`, `styles.css`, `app.js` based on text + visual cues.
5. **Validates** the HTML (deterministic: must contain `<header>`, hero, `<footer>`). On failure it injects a synthetic `OBSERVE` listing what's missing — a single, cheap reflection trigger.
6. **Screenshots its own output**, looks at *that*, compares against the source. If the gap is significant, it edits and redoes one visual pass.
7. **Opens it in a browser** and emits `OUTPUT`.
8. A separate post-run **`MemoryWriter`** decides what to persist to `MEMORY.md`.

---

## Design philosophy

Five ideas drive everything in the codebase. Each one has consequences in the file layout, so they're not just talk.

### 1. Context is the product

A model's behavior is a function of what enters its context window. Before changing the model or the prompt, ask: *what is the model seeing, in what order, with what salience?*

Concretely:
- The system prompt is **layered** (`[SYSTEM] [TASK] [MEMORY] [SUMMARY] [REMINDER]`) — see [`agent/context.py`](src/scaler_cloner/agent/context.py).
- Old turns past the recent window collapse to one-line bullets so token cost stays flat across long runs.
- The schema reminder is repeated at the bottom of the system block — recency + primacy.
- The stable prefix (system) is sent separately from volatile content (history + current message) so prompt caching has something to bite on.

### 2. Reasoning pattern, picked deliberately

This is **ReAct + bounded reflection** — not vanilla CoT, not plan-and-execute, not multi-agent debate.

- *ReAct* because the task interleaves *thinking* (designing HTML/CSS) with *acting* (fetching, screenshotting, writing files).
- *Bounded reflection* (one corrective pass at most), driven by a **deterministic validator**, not a free-running self-critique loop. Self-critique loops are where agents go to die — they tend to chase phantom problems and never terminate. The validator says "missing footer", once, and only when there actually is no footer.

### 3. Determinism where possible, LLM where necessary

Push deterministic logic out of the model. The LLM is reserved for genuinely fuzzy steps.

| Concern                            | Owner               |
|------------------------------------|---------------------|
| URL extraction from user request   | regex (`agent/url.py`) |
| Path traversal refusal             | `tools/_sandbox.py`    |
| HTML validation                    | `selectolax` (`agent/validator.py`) |
| Memory budget enforcement          | `agent/memory.py`      |
| JSON parsing of model output       | `agent/llm.py`         |
| Run-id injection into tool calls   | `agent/loop.py`        |
| **The actual cloning judgment**    | **Gemini**            |

### 4. Trust boundaries, made explicit

Every input has a posture.

| Surface          | Trusted to do                              | Forbidden                          |
|------------------|--------------------------------------------|------------------------------------|
| User input       | name a goal                                | execute as code                    |
| Tool output      | be summarized into context                 | be echoed raw or executed          |
| Model output     | dispatch tools after validation            | dispatch without parsing           |
| Vision response  | flow into the loop as text                 | flow back as raw image bytes       |

`fetch_url` deliberately returns a *summary*, never raw HTML. `look_at` returns *text observations*, never raw image bytes. This is what keeps the main reasoning loop text-only and cheap, even though we use vision.

### 5. Smallest agent that works

It would be easy to design this as five agents (researcher → designer → coder → reviewer → writer) with a graph in between. We didn't. **One ReAct loop**, one validator, one separate writer for memory. Each split adds latency, failure modes, and context loss; we only pay that cost where it earns its keep — namely, isolating memory writes into a separate `MemoryWriter` so the main loop can't pollute its own future context.

---

## Architecture

```
src/scaler_cloner/
├── cli.py                  entrypoint — TUI by default, --headless for stdout
├── config.py               env loader + budgets (max_steps, max_tool_calls)
├── events.py               async EventBus — agent publishes, TUI consumes
│                           (the agent never imports the TUI)
│
├── tui/
│   ├── app.py              Textual root — composes layout, runs agent task
│   ├── theme.tcss          CSS-like styles, rounded orange input border
│   └── widgets/
│       ├── chat_log.py     scrollable event renderer
│       ├── input_box.py    rounded-border prompt
│       ├── thinking.py     pulsating ●  + verb cycler (Claude-Code style)
│       └── status_bar.py   model · steps · tools · run-id
│
├── agent/
│   ├── schema.py           Pydantic AgentStep / Turn / MemoryPatch
│   ├── url.py              extract https://… or bare host from the request
│   ├── context.py          layered prompt assembler (the heart of context eng)
│   ├── prompts/
│   │   ├── system.md       identity + rules + tool catalog placeholder
│   │   └── examples.md     few-shot
│   ├── llm.py              Gemini wrapper — JSON-mode, retry, fence-stripping,
│   │                       balanced-brace JSON extraction
│   ├── loop.py             ReAct executor; injects validator OBSERVEs
│   ├── validator.py        deterministic header/hero/footer check
│   ├── memory.py           MEMORY.md parse / render / patch / budget
│   └── memory_writer.py    post-run summarizer (separate trust boundary)
│
└── tools/
    ├── _sandbox.py         resolve paths inside output/<run-id>/, refuse traversal
    ├── registry.py         single source of truth: TOOL_MAP + TOOL_SCHEMAS
    ├── fetch_url.py        httpx + selectolax → summary (never raw HTML)
    ├── screenshot_url.py   Playwright headless Chromium → PNG in sandbox
    ├── look_at.py          Gemini Vision → free-form observations text
    ├── write_file.py
    ├── read_file.py
    ├── list_dir.py
    └── open_browser.py
```

Tests live in [`tests/`](tests/). The `tests/` tree mirrors the source tree.

---

## The agent loop in detail

Every turn the loop builds a context and asks Gemini for the next step.

```
build_context(transcript, target_url, memory_block) -> BuiltContext
  ├─ system  = [SYSTEM] [TASK target_url] [MEMORY host-scoped]
  │              [SUMMARY older turns compressed] [REMINDER]
  ├─ history = last N turns verbatim (alternating user/assistant)
  └─ current = the prompt to react to
```

The model emits **one JSON `AgentStep`** per turn. The runtime parses + validates + dispatches:

| Step kind | What the runtime does                                                       |
|-----------|------------------------------------------------------------------------------|
| `START`   | publishes a `step_started` event                                             |
| `THINK`   | publishes a `think` event; nothing else                                      |
| `TOOL`    | dispatches via `TOOL_MAP[name]`; injects `run_id` for sandboxed tools; appends an `OBSERVE` turn with the result |
| `OBSERVE` | (model is not allowed to author this — runtime corrects it)                  |
| `OUTPUT`  | publishes `output`, runs `MemoryWriter`, returns                             |

After a successful `index.html` write, the runtime *also* runs the deterministic [`validator.py`](src/scaler_cloner/agent/validator.py) and appends a synthetic `OBSERVE` with the verdict. If header/hero/footer is missing, the agent has to fix it before progressing.

### Termination is bounded

- `max_steps = 25`
- `max_tool_calls = 8`
- ~120k token ceiling (model-side)
- explicit `OUTPUT` step
- if the user request has no URL, the loop terminates **before** the first LLM call

### The event bus is the seam

`agent/loop.py` publishes typed `AgentEvent`s onto an `asyncio.Queue` ([`events.py`](src/scaler_cloner/events.py)). The TUI consumes them. **The agent never imports the TUI.** This is the seam that lets you swap in a plain stdout renderer (`--headless` mode) without changing a line of agent code, and it's also what makes testing the loop with a scripted fake LLM trivial.

---

## Long-term memory — `MEMORY.md`

The agent maintains a single Markdown file at the project root. Three sections, each with its own token budget:

| Section            | Budget (tokens) | Behavior                                    |
|--------------------|-----------------|---------------------------------------------|
| User preferences   | 500             | global; free-form                           |
| Site knowledge     | 1500            | **per-host buckets** (`### scaler.com` etc.)|
| Run log            | 1000            | **FIFO** — oldest entries drop on overflow  |

### Special methods

- **Per-host scoping.** When you clone `stripe.com`, only the `### stripe.com` bucket of Site knowledge is loaded into context. Cloning `scaler.com` later doesn't pollute that context with Stripe facts. Implementation: [`Memory.site_bucket(host)`](src/scaler_cloner/agent/memory.py).
- **Token-budget enforcement on every write.** Free-form sections truncate from the top; the run log drops oldest lines (FIFO). Implementation: [`_enforce_budget`](src/scaler_cloner/agent/memory.py).
- **Approximate token counting** as `chars / 4` — good enough for budget guards. The hard token ceiling at the model API is a separate, stricter check.
- **Read/write split.** The main reasoning loop **reads** memory at the start of a run. Only the post-run [`MemoryWriter`](src/scaler_cloner/agent/memory_writer.py) **writes**. This is the trust boundary that prevents the agent from writing to its own future context mid-run — the most common failure mode in long-horizon agents.
- **`MemoryWriter` runs on the cheap model.** Memory summarization is not reasoning; it's compression. Uses `gemini-2.5-flash`.
- **Best-effort writes.** A `MemoryWriter` failure never fails the run. Memory is a nice-to-have, not load-bearing.
- **Structured patches**, not free-form rewrites. The writer emits `[{section, op, content}, …]` patches that the deterministic `apply_patch` applies. The writer can't accidentally clobber the file.

### What gets saved (and what doesn't)

- ✅ User preferences (`"I like minimalist CSS"` → User preferences)
- ✅ Concrete site facts (`"scaler.com palette: #00…"` → Site knowledge[scaler.com])
- ✅ A 1-line run-log entry every run
- ❌ Anything already documented in code or git history
- ❌ The transcript (it's ephemeral; collapse it, don't persist it)

---

## Code walkthrough

A 3-minute tour, in the order I'd recommend reading:

1. **[`agent/schema.py`](src/scaler_cloner/agent/schema.py)** — the wire format (`AgentStep`, `Turn`, `MemoryPatch`). Read this first; everything else flows through these types.
2. **[`tools/_sandbox.py`](src/scaler_cloner/tools/_sandbox.py)** — the path-resolution helper. Two functions, refuses traversal.
3. **[`tools/registry.py`](src/scaler_cloner/tools/registry.py)** — the tool catalog. One source of truth: name, JSON schema, callable. The `injects_run_id` flag tells the loop which tools get `run_id` automatically.
4. **[`tools/fetch_url.py`](src/scaler_cloner/tools/fetch_url.py)** — httpx + selectolax. Note: returns a *summary*, never raw HTML.
5. **[`tools/screenshot_url.py`](src/scaler_cloner/tools/screenshot_url.py)** — Playwright. Bare paths auto-resolve to `file://` URIs so the agent can screenshot its own output.
6. **[`tools/look_at.py`](src/scaler_cloner/tools/look_at.py)** — Gemini Vision. Returns a ≤2KB observations string. The main loop never sees image bytes.
7. **[`agent/url.py`](src/scaler_cloner/agent/url.py)** — extract a URL or bare host from the user's free-form request.
8. **[`agent/context.py`](src/scaler_cloner/agent/context.py)** — the layered prompt assembler. The `[SYSTEM] [TASK] [MEMORY] [SUMMARY] [REMINDER]` ordering, compression of older turns, schema reminder injection.
9. **[`agent/llm.py`](src/scaler_cloner/agent/llm.py)** — Gemini wrapper. JSON mode + retry + markdown-fence stripping + balanced-brace extraction (handles braces inside string content and prefix/suffix prose).
10. **[`agent/validator.py`](src/scaler_cloner/agent/validator.py)** — deterministic check for `<header>`, hero, `<footer>`. Hero detection uses a small heuristic (class/id hints + section-with-heading + `<main> > <h1>`).
11. **[`agent/memory.py`](src/scaler_cloner/agent/memory.py)** — parse, render, patch, budget. The per-host bucket logic lives in `_set_or_append_host_bucket`.
12. **[`agent/memory_writer.py`](src/scaler_cloner/agent/memory_writer.py)** — post-run patch generator on the cheap model.
13. **[`agent/loop.py`](src/scaler_cloner/agent/loop.py)** — the ReAct executor. Reads top to bottom; the dispatch logic is at the bottom.
14. **[`events.py`](src/scaler_cloner/events.py)** — typed `AgentEvent` + `EventBus`. ~30 LOC.
15. **[`tui/app.py`](src/scaler_cloner/tui/app.py)** — Textual root. Composes the layout, runs the agent in a background task, drains the event bus into widgets.
16. **[`tui/widgets/thinking.py`](src/scaler_cloner/tui/widgets/thinking.py)** — the pulsating orange bubble. Single `●` glyph lerping between `#FF6B1A` ↔ `#FFA559` on a 1.2s sine; 12-verb rotation every 1.8s.

---

## Setup

```bash
git clone https://github.com/dibyo10/gen_ai_assignment_cli
cd gen_ai_assignment_cli

python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium  # ~150MB one-time download

cp .env.example .env
# Edit .env and set GEMINI_API_KEY=…
```

You need a Gemini API key. Get one at [aistudio.google.com](https://aistudio.google.com/) — the free tier is plenty for this.

---

## Running it

### TUI (default)

```bash
.venv/bin/site-cloner
```

Then type any of:
- `clone https://scaler.com`
- `clone stripe.com`
- `clone vercel.com with a teal palette`
- `clone https://news.ycombinator.com`

Quit: `ctrl+c`. Clear chat: `ctrl+l`. Focus input: `esc`.

### Headless (great for the demo recording — no TUI cursor weirdness)

```bash
.venv/bin/site-cloner --headless                          # defaults to scaler.com
.venv/bin/site-cloner --headless "clone https://stripe.com"
.venv/bin/site-cloner --headless "clone vercel.com but with a warm orange palette"
```

### Output

Each run gets its own directory under `output/`:

```
output/
  20260506-224501-a3f9c2/
    index.html
    styles.css
    app.js
    _ref/
      source.png    # screenshot of the source site
      mine.png      # screenshot of YOUR cloned page
```

Open `index.html` in any browser; everything is plain static HTML/CSS/JS, no build step.

---

## Testing

```bash
.venv/bin/pytest -q
# 62 passed in 2.67s
```

Coverage:
- sandbox traversal refusal
- write/read/list roundtrip
- `fetch_url` against an in-process httpx mock (no network)
- `screenshot_url` real-render of a local HTML file (skipped if Playwright missing)
- `look_at` with a fake Gemini client
- URL extraction (https://…, bare hosts, subdomains, none, multiple)
- context layering, target-URL injection, compression after window
- LLM JSON parsing (fences, prose prefixes, nested/string braces, invalid kinds)
- end-to-end loop with a scripted client (write+OUTPUT, unknown tool, step budget, no-URL early exit)
- validator (presence + hero heuristics + soft notes)
- reflection trigger (bad → synthetic OBSERVE → good)
- memory: parse/render/patch, **per-host bucket isolation**, FIFO budget
- TUI compose + resize at 4 sizes + thinking-bubble lifecycle

---

## Demo recipe

For the 2–3 minute video:

1. `cat .env` — show the key is set.
2. `.venv/bin/site-cloner` — TUI launches; show the rounded orange input box.
3. Type `clone https://scaler.com`, hit enter.
4. Watch the ● pulse and verbs cycle: `thinking → fetching → checking → weaving → cooking`.
5. Tool calls stream in: `fetch_url ✓`, `screenshot_url ✓`, `look_at ✓`, `write_file index.html ✓`, validator ◇ OK, `screenshot_url(index.html) ✓`, `look_at(mine.png) ✓`, comparison `THINK`, optional `write_file styles.css ✓`, `open_in_browser ✓`.
6. Browser opens; show the cloned page.
7. Quit (`ctrl+c`). `ls output/<run-id>/` — show the four files + `_ref/` screenshots.
8. Run again with a different URL: `.venv/bin/site-cloner --headless "clone https://stripe.com"`. Show the same flow against a totally different site.
9. `cat MEMORY.md` — show that the agent has accumulated **per-host** site knowledge (separate `### scaler.com` and `### stripe.com` buckets) and a FIFO run log.

---

## License

MIT.
