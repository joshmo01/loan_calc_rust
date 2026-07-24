# Structured Loan Calculator (share package)

Two ways to use this package:

| Mode | Needs network? | Needs API key? | How |
|------|----------------|----------------|-----|
| **A. Chat + WASM** | Yes (Cerebras) | Yes | `./start-chat.sh` or `start-chat.command` |
| **B. Offline form** | No | No | Open `standalone/loan-calculator-standalone.html` |

- **Loan math** always runs in **Rust WebAssembly** in the browser.
- **Chat** only extracts parameters via Cerebras (Gemma 4); it does not invent EMI numbers.

## Requirements

- **Python 3.9+** (for chat server only)
- Modern browser (Chrome / Edge / Firefox / Safari)
- For chat: [Cerebras API key](https://cloud.cerebras.ai)

## A. Start chat UI (macOS / Linux)

```bash
export CEREBRAS_API_KEY='csk-...'   # your key — do not commit or email this
./start-chat.sh
```

Or double-click **`start-chat.command`** on macOS (after setting the key in Terminal once, or editing the script to read from `.env`).

Then open: **http://localhost:8790/**

### Optional `.env` file

```bash
cp .env.example .env
# edit .env and set CEREBRAS_API_KEY
./start-chat.sh
```

## B. Offline calculator only

Double-click:

`standalone/loan-calculator-standalone.html`

No install, no server, no API key.

## Security

- Never put API keys in HTML or share them in chat/email if avoidable.
- Each person should use **their own** Cerebras key.
- Do not upload this zip to a public repo with a real `.env` inside.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `CEREBRAS_API_KEY is not set` | `export CEREBRAS_API_KEY=csk-...` then restart |
| Port in use | `PORT=8791 ./start-chat.sh` |
| WASM not loading | Use the chat server URL, not `file://` for chat mode |
| Chat 429 / high traffic | Retry; Cerebras queue may be busy |
| Offline HTML stuck | Use the file under `standalone/` from this zip |

## What’s inside

```
chat/          Python proxy + web UI + WASM
standalone/    Single-file offline calculator
start-chat.sh  Launch script (Unix)
start-chat.command  macOS double-click launcher
.env.example   Config template
README.md      This file
```
