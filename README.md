# vibe-coder

A conversational CLI agent that clones any website you point it at — built in the spirit of **Cursor**, **Windsurf**, and **Claude Code**, with a Codex-style monochrome TUI.

Powered by **Gemini 2.5 Pro** (reasoning) and **Gemini 2.5 Flash** (vision).

```
██╗   ██╗██╗██████╗ ███████╗      ██████╗ ██████╗ ██████╗ ███████╗██████╗
██║   ██║██║██╔══██╗██╔════╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
██║   ██║██║██████╔╝█████╗       ██║     ██║   ██║██║  ██║█████╗  ██████╔╝
╚██╗ ██╔╝██║██╔══██╗██╔══╝       ██║     ██║   ██║██║  ██║██╔══╝  ██╔══██╗
 ╚████╔╝ ██║██████╔╝███████╗     ╚██████╗╚██████╔╝██████╔╝███████╗██║  ██║
  ╚═══╝  ╚═╝╚═════╝ ╚══════╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

a clone specialist · point it at a URL · ⌘+c to quit
```

---

## What it does

You type `clone https://stripe.com` (or just `stripe.com`). The agent:

1. **Fetches** the page and extracts a structured summary — title, description, section outline, dominant colors, cleaned text — without dumping raw HTML into its context.
2. **Screenshots** the page with **headless Chromium** (Playwright) into the run sandbox.
3. **Looks at** that PNG with **Gemini Vision** and gets back free-form observations (palette, header layout, hero composition, sections, footer, typography vibe).
4. **Drafts** `index.html`, `styles.css`, `app.js`.
5. **Validates** the HTML deterministically — must contain `<header>`, hero, `<footer>`. On failure it injects a synthetic `OBSERVE` listing what's missing — a single, cheap reflection trigger.
6. **Screenshots its own output**, looks at *that*, and compares against the source. One visual pass; no infinite self-critique loop.
7. **Opens it in a browser** and emits `OUTPUT`.

---

## Design philosophy

Five ideas drive everything in the codebase.

### 1. Context is the product
A model's behavior is a function of what enters the context window. The system prompt is layered (`[SYSTEM] [TASK] [MEMORY] [SUMMARY] [REMINDER]`), older turns collapse to one-line bullets to keep token cost flat, and the schema reminder is repeated at the bottom for recency + primacy.

### 2. Reasoning pattern, picked deliberately
**ReAct + bounded reflection.** Not vanilla CoT (no tools), not plan-and-execute (re-planning is cheap here), not multi-agent debate (overkill). The "reflection" is a deterministic validator, not a free-running self-critique loop — those are where agents go to die.

### 3. Determinism where possible, LLM where necessary
Push deterministic logic out of the model:

| Concern                          | Owner                           |
|----------------------------------|---------------------------------|
| URL extraction from request      | regex (`agent/url.py`)          |
| Path traversal refusal           | `tools/_sandbox.py`             |
| HTML validation                  | `selectolax` (`agent/validator.py`) |
| JSON parsing of model output     | `agent/llm.py`                  |
| Run-id injection into tools      | `agent/loop.py`                 |
| **The actual cloning judgment**  | **Gemini**                      |

### 4. Trust boundaries, made explicit

| Surface          | Trusted to do                  | Forbidden                        |
|------------------|--------------------------------|----------------------------------|
| User input       | name a goal                    | execute as code                  |
| Tool output      | summarized into context        | echoed raw or executed           |
| Model output     | dispatch tools after validation| dispatch without parsing         |
| Vision response  | flow into the loop as text     | flow back as raw image bytes     |

`fetch_url` returns a *summary*, never raw HTML. `look_at` returns *text observations*, never image bytes. The main loop stays text-only and cheap, even though we use vision.

### 5. Smallest agent that works
One ReAct loop, one validator. Could have been five-agent graph; would have added latency, failure modes, and context loss. We only paid that cost where it earns its keep.

---

## Architecture

```
src/scaler_cloner/
├── cli.py                  entrypoint — TUI by default, --headless for stdout
├── config.py               env loader + budgets (max_steps, max_tool_calls)
├── events.py               async EventBus — agent publishes, TUI consumes
│                           (the agent never imports the TUI)
│
├── tui/                    Codex-style monochrome
│   ├── app.py              Textual root
│   ├── theme.tcss          dim greys, single soft amber accent
│   └── widgets/
│       ├── banner.py       VIBE-CODER block letters on mount
│       ├── chat_log.py     scrollable monochrome event log
│       ├── input_box.py    flat '>' caret + Input (no border)
│       ├── thinking.py     subtle ▪ tick + dim verb cycler
│       └── status_bar.py   model · steps · tools · run-id
│
├── agent/
│   ├── schema.py           Pydantic AgentStep / Turn / MemoryPatch
│   ├── url.py              extract https://… or bare host from request
│   ├── context.py          layered prompt assembler
│   ├── prompts/
│   │   ├── system.md       VIBE-CODER identity + rules + tool catalog
│   │   └── examples.md     few-shot
│   ├── llm.py              Gemini wrapper — JSON-mode + retry +
│   │                       fence-stripping + balanced-brace JSON extraction
│   ├── loop.py             ReAct executor; injects validator OBSERVEs
│   └── validator.py        deterministic header/hero/footer check
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

Tests in [`tests/`](tests/) mirror the source tree.

---

## The agent loop in detail

Every turn the loop builds a context and asks Gemini for the next step.

```
build_context(transcript, target_url) -> BuiltContext
  ├─ system  = [SYSTEM] [TASK target_url]
  │              [SUMMARY older turns compressed] [REMINDER]
  ├─ history = last N turns verbatim (alternating user/assistant)
  └─ current = the prompt to react to
```

The model emits **one JSON `AgentStep`** per turn. The runtime parses, validates, and dispatches:

| Step kind | What the runtime does                                                         |
|-----------|--------------------------------------------------------------------------------|
| `START`   | publishes a `step_started` event                                               |
| `THINK`   | publishes a `think` event                                                      |
| `TOOL`    | dispatches via `TOOL_MAP[name]`; injects `run_id` for sandboxed tools; appends `OBSERVE` turn with the result |
| `OBSERVE` | (model is not allowed to author this — runtime corrects it)                    |
| `OUTPUT`  | publishes `output`, returns                                                    |

After a successful `index.html` write, the runtime *also* runs the deterministic [`validator.py`](src/scaler_cloner/agent/validator.py) and appends a synthetic `OBSERVE` with the verdict. Header/hero/footer missing? The agent has to fix it before progressing.

### Termination is bounded
- `max_steps = 25`
- `max_tool_calls = 8`
- ~120k token ceiling
- explicit `OUTPUT` step
- if the request has no URL, the loop exits **before** the first LLM call

### The event bus is the seam
`agent/loop.py` publishes typed `AgentEvent`s onto an `asyncio.Queue` ([`events.py`](src/scaler_cloner/events.py)). The TUI consumes them. **The agent never imports the TUI.** That seam is what lets `--headless` mode work without changing a line of agent code, and why scripted-LLM tests are trivial.

---

## A note on memory

Earlier builds maintained a live `MEMORY.md` at the project root with three token-budgeted sections (User preferences, per-host Site knowledge, FIFO Run log) and a separate post-run `MemoryWriter` step that had the *only* write access — keeping the main reasoning loop from polluting its own future context.

The current build keeps `MEMORY.md` as a **static design artifact** only — the file is no longer read or written at runtime. The writer code is preserved in the tree as documentation.

---

## Setup

```bash
git clone https://github.com/Adhyayan2107/genai_cli
cd genai_cli

python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium  # ~150MB one-time download

cp .env.example .env
# Edit .env and set GEMINI_API_KEY=…
```

Get a Gemini API key at [aistudio.google.com](https://aistudio.google.com/) — the free tier is plenty.

---

## Running it

### TUI (default)
```bash
.venv/bin/site-cloner
```
Then type:
- `clone https://scaler.com`
- `clone stripe.com`
- `clone vercel.com with a teal palette`
- `clone https://news.ycombinator.com`

Quit: `ctrl+c`. Clear chat: `ctrl+l`. Focus input: `esc`.

### Headless (clean stdout — great for the demo recording)
```bash
.venv/bin/site-cloner --headless                          # defaults to scaler.com
.venv/bin/site-cloner --headless "clone https://stripe.com"
.venv/bin/site-cloner --headless "clone vercel.com but with a warm orange palette"
```

### Output
Each run gets its own directory:
```
output/
  20260506-235333-415614/
    index.html
    styles.css
    app.js
    _ref/
      source.png    # screenshot of the source site
      mine.png      # screenshot of YOUR cloned page
```
Open `index.html` in any browser. Plain static HTML/CSS/JS; no build step.

---

## Testing

```bash
.venv/bin/pytest -q
```

Coverage:
- sandbox traversal refusal
- write/read/list roundtrip
- `fetch_url` against an in-process httpx mock (no network)
- `screenshot_url` real-render of a local HTML file
- `look_at` with a fake Gemini client
- URL extraction (https://…, bare hosts, subdomains, none, multiple)
- context layering, target-URL injection, compression after window
- LLM JSON parsing (fences, prose prefixes, nested/string braces, invalid kinds)
- end-to-end loop with a scripted client (write+OUTPUT, unknown tool, step budget, no-URL early exit)
- validator (presence + hero heuristics + soft notes)
- reflection trigger (bad → synthetic OBSERVE → good)
- TUI compose + resize at 4 sizes + thinking-bubble lifecycle + **keystroke roundtrip on the Input**

---

## Demo recipe

For the 2–3 min video:

1. `cat .env` — show the key is set.
2. `.venv/bin/site-cloner` — TUI launches; show the **VIBE-CODER** banner drop in.
3. Type `clone https://scaler.com`, hit enter.
4. Watch the ▪ tick and verbs cycle: `thinking → fetching → checking → weaving → cooking`.
5. Tool calls stream in: `fetch_url ✓`, `screenshot_url ✓`, `look_at ✓`, `write_file index.html ✓`, validator ◇ OK, `screenshot_url(index.html) ✓`, `look_at(mine.png) ✓`, optional comparison + edit pass, `open_in_browser ✓`.
6. Browser opens; show the cloned page.
7. Quit (`ctrl+c`). `ls output/<run-id>/` — show the four files + `_ref/` screenshots.
8. Run again with a different URL: `.venv/bin/site-cloner --headless "clone https://stripe.com"`. Show the same flow against a totally different site.

---

## Author

**Adhyayan Gupta** — built as Assignment 02.

## License

MIT.
