# Build Plan

## Stack
- Python 3.11+, `uv` for packaging
- Gemini 2.5 Pro (reasoning) + Flash (cheap dispatch steps)
- Textual for TUI (rounded borders, reactive resize)
- Custom ReAct loop (no LangChain — task is small enough that framework overhead would obscure the reasoning pattern)

## Agent loop — context layering
```
[SYSTEM]   identity, schema, hard rules, tool catalog
[TASK]     cloning goal + acceptance (header/hero/footer)
[MEMORY]   relevant sections from MEMORY.md
[SUMMARY]  compressed summary of completed steps (after step 6)
[RECENT]   last 3 turns verbatim
[CURRENT]  user message OR last OBSERVE
[REMINDER] schema repeated at the bottom
```

## Termination budget
- max 25 steps
- max 8 tool calls
- ~120k token ceiling

## Tools (5)
- `fetch_url(url)` — returns title + cleaned text + color tokens + section outline (never raw HTML to the model)
- `write_file(path, content)` — sandboxed under `./output/<run-id>/`
- `read_file(path)` — for self-verification
- `list_dir(path)` — orientation
- `open_in_browser(path)` — final step

## Validator (deterministic)
After every `index.html` write, parse with selectolax. Must contain `<header>`, a hero section, `<footer>`. If missing, inject a synthetic OBSERVE — single reflection trigger.

## Memory
`./MEMORY.md` — three sections, token-budgeted:
- User preferences (500)
- Site knowledge (1500)
- Run log (1000, FIFO)

Main loop reads; only the post-run `MemoryWriter` step writes.

## Build order
1. Repo skeleton
2. Tool layer (no LLM) + tests
3. Schema + context builder
4. Gemini client + JSON mode
5. Headless agent loop — MVP
5.5 Memory layer
6. Validator + reflection
7. Textual TUI shell
8. Event bus wiring
9. Thinking bubble + verb cycler
10. Resize / small-terminal QA
11. README + demo recording
