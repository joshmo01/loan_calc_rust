#!/usr/bin/env python3
"""
Loan Calculator Chat server
  - Serves the chat UI + WASM static files
  - Proxies chat to an OpenAI-compatible LLM API
  - Default provider: **Cerebras** (Gemma 4 31B)
  - API key stays server-side (never exposed to the browser)

Env:
  CEREBRAS_API_KEY   preferred API key for Cerebras
  LLM_API_KEY        fallback key (also used for other providers)
  LLM_BASE_URL       default https://api.cerebras.ai/v1
  LLM_MODEL          default gemma-4-31b
  PORT               default 8790

Examples:
  # Cerebras (default)
  export CEREBRAS_API_KEY=csk-...
  python3 chat/server.py

  # Cerebras with explicit model
  CEREBRAS_API_KEY=csk-... LLM_MODEL=gemma-4-31b python3 chat/server.py

  # Local Ollama instead
  LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=gemma3:4b python3 chat/server.py
"""

from __future__ import annotations

import json
import os
import re
import traceback
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WWW = ROOT / "www"
PORT = int(os.environ.get("PORT", "8790"))

# Cerebras OpenAI-compatible Inference API
# Docs: https://inference-docs.cerebras.ai/resources/openai
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.cerebras.ai/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma-4-31b")
LLM_API_KEY = (
    os.environ.get("CEREBRAS_API_KEY")
    or os.environ.get("LLM_API_KEY")
    or os.environ.get("XAI_API_KEY")
    or ""
)
IS_CEREBRAS = "cerebras.ai" in LLM_BASE_URL

SYSTEM_PROMPT = """You are a structured-loan assistant for a browser calculator powered by a Rust WASM engine.

Your job:
1) Chat helpfully about loan products (EMI, balloon, interest-only, moratorium, step-up, fees, day-count, IRR).
2) Extract loan parameters from the conversation.
3) When enough parameters exist to run a calculation, set ready_to_calculate=true.

ALWAYS respond with a single JSON object only (no markdown fences, no prose outside JSON):
{
  "reply": "short friendly message to the user",
  "params": {
    "principal": number|null,
    "annual_rate_pct": number|null,
    "term_months": number|null,
    "frequency": "monthly"|"quarterly"|"half-yearly"|"yearly"|null,
    "day_count": "30/360"|"Actual/365"|"Actual/360"|null,
    "start_date": "YYYY-MM-DD"|null,
    "first_payment_date": "YYYY-MM-DD"|null,
    "fees": number|null,
    "commission": number|null,
    "subvention": number|null,
    "structure": "emi"|"interest_only"|"balloon"|"moratorium_emi"|"step_up"|null,
    "moratorium_periods": number|null,
    "balloon_periods": number|null,
    "balloon_payment": number|null,
    "step_growth_pct": number|null
  },
  "ready_to_calculate": boolean,
  "missing_fields": ["..."]
}

Rules:
- Only fill fields the user stated or clearly implied; otherwise null.
- Minimum to calculate: principal, annual_rate_pct, term_months.
- Default frequency monthly, day_count 30/360, structure emi when unspecified but ready.
- Dates as YYYY-MM-DD if given; else null (UI has defaults).
- structure mapping:
  - standard EMI / term loan → "emi"
  - interest only → "interest_only"
  - balloon → "balloon" (+ balloon_periods, balloon_payment if known)
  - moratorium / payment holiday → "moratorium_emi" (+ moratorium_periods if known)
  - step-up → "step_up" (+ step_growth_pct if known)
- If user asks to recalculate with changes, update params and set ready_to_calculate true.
- reply should confirm what you understood and ask only for missing critical fields.
- JSON must be valid and parseable.
"""


def llm_chat(messages: list[dict]) -> str:
    """Call OpenAI-compatible /chat/completions and return assistant content."""
    if not LLM_API_KEY and IS_CEREBRAS:
        raise RuntimeError(
            "CEREBRAS_API_KEY is not set. Get a key at https://cloud.cerebras.ai "
            "then: export CEREBRAS_API_KEY=csk-..."
        )

    url = f"{LLM_BASE_URL}/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    # JSON mode where supported. Cerebras structured outputs work with response_format
    # on many models; if a model rejects it, we still parse fenced JSON from the reply.
    if IS_CEREBRAS or "openrouter" in LLM_BASE_URL or "api.x.ai" in LLM_BASE_URL:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "structured-loan-wasm-chat/1.0",
    }
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        # Retry once without response_format if Cerebras rejects it
        if e.code == 400 and "response_format" in payload and IS_CEREBRAS:
            payload.pop("response_format", None)
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e2:
                err_body2 = e2.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Cerebras HTTP {e2.code}: {err_body2[:800]}") from e2
        else:
            raise RuntimeError(f"LLM HTTP {e.code}: {err_body[:800]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach LLM at {LLM_BASE_URL} ({e.reason}). "
            f"For Cerebras set CEREBRAS_API_KEY; for Ollama start the local server."
        ) from e

    try:
        content = body["choices"][0]["message"]["content"]
        # Some models return content as a list of parts
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LLM response: {json.dumps(body)[:500]}") from e


def extract_json_object(text: str) -> dict:
    """Parse model output into a dict; tolerate ```json fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last-resort: first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/health":
            return self._json(
                200,
                {
                    "ok": True,
                    "provider": "cerebras" if IS_CEREBRAS else "openai-compatible",
                    "model": LLM_MODEL,
                    "base_url": LLM_BASE_URL,
                    "has_api_key": bool(LLM_API_KEY),
                },
            )
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/chat":
            return self._handle_chat()
        self.send_error(404, "Not found")

    def _handle_chat(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8") or "{}")
            history = body.get("messages") or []
            # history: [{role, content}, ...] user/assistant only
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for m in history[-20:]:
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and isinstance(content, str):
                    messages.append({"role": role, "content": content})

            if len(messages) < 2:
                return self._json(400, {"error": "messages required"})

            content = llm_chat(messages)
            parsed = extract_json_object(content)

            # normalize shape
            reply = parsed.get("reply") or "OK"
            params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
            ready = bool(parsed.get("ready_to_calculate"))
            missing = parsed.get("missing_fields") or []
            if not isinstance(missing, list):
                missing = []

            return self._json(
                200,
                {
                    "reply": reply,
                    "params": params,
                    "ready_to_calculate": ready,
                    "missing_fields": missing,
                    "model": LLM_MODEL,
                    "raw": content,
                },
            )
        except Exception as e:
            traceback.print_exc()
            return self._json(502, {"error": str(e)})

    def _json(self, status: int, obj: dict):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def main():
    if not WWW.is_dir():
        raise SystemExit(f"www not found: {WWW}")
    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer(("", PORT), Handler) as httpd:
        provider = "Cerebras" if IS_CEREBRAS else "OpenAI-compatible"
        print(f"Structured Loan Chat (WASM + {provider})")
        print(f"  UI:        http://localhost:{PORT}/")
        print(f"  LLM:       {LLM_BASE_URL}")
        print(f"  model:     {LLM_MODEL}")
        key_state = "set" if LLM_API_KEY else (
            "MISSING — export CEREBRAS_API_KEY=..." if IS_CEREBRAS else "not set"
        )
        print(f"  API key:   {key_state}")
        print("  Health:    GET /api/health")
        print("  Chat:      POST /api/chat")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
