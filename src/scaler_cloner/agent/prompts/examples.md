The user will ask you to clone the Scaler website. A typical run looks like:

assistant: { "step": "START", "content": "User wants a static clone of scaler.com. I need a reference to match the layout and palette." }

assistant: { "step": "THINK", "content": "Plan: 1) fetch_url scaler.com for outline+colors, 2) write index.html, styles.css, app.js, 3) read_file to verify, 4) open_in_browser." }

assistant: { "step": "TOOL", "tool_name": "fetch_url", "tool_args": { "url": "https://scaler.com" } }

developer: { "step": "OBSERVE", "content": "{ ok: true, title: 'Scaler — ...', outline: [header, hero, footer, ...], colors: ['#0066ff', '#0a0a0a', ...], text: '...' }" }

assistant: { "step": "THINK", "content": "Got palette and outline. Header has logo + nav + CTA; hero has H1+sub+CTA; footer has links. Drafting HTML." }

assistant: { "step": "TOOL", "tool_name": "write_file", "tool_args": { "path": "index.html", "content": "<!doctype html>...<header>...</header>...<section class=\"hero\">...</section>...<footer>...</footer>" } }

developer: { "step": "OBSERVE", "content": "{ ok: true, path: 'index.html', bytes: 4321 }" }

(continues with styles.css, app.js, then open_in_browser, then OUTPUT)
