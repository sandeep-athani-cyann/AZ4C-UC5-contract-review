"""Small OpenAI-compatible chat client for Groq (primary) and Gemini (fallback).

Uses only the standard library. Keys and addresses come from the environment
(GROQ_API_KEY, GROQ_BASE_URL, GEMINI_API_KEY, GEMINI_BASE_URL). When no key is set,
available() is False and the agents run on their deterministic rules alone.
"""
import json
import os
import random
import time
import urllib.error
import urllib.request

RETRY_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    pass


def _providers() -> list[dict]:
    out = []
    if os.environ.get("GROQ_API_KEY") and os.environ.get("GROQ_BASE_URL"):
        out.append({
            "name": "groq",
            "url": os.environ["GROQ_BASE_URL"].rstrip("/") + "/openai/v1/chat/completions",
            "key": os.environ["GROQ_API_KEY"],
            "model": os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile",
        })
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_BASE_URL"):
        out.append({
            "name": "gemini",
            "url": os.environ["GEMINI_BASE_URL"].rstrip("/") + "/v1beta/openai/chat/completions",
            "key": os.environ["GEMINI_API_KEY"],
            "model": os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash",
        })
    return out


def available() -> bool:
    return os.environ.get("LLM_DISABLED", "").lower() not in ("1", "true", "yes") and bool(_providers())


def _post(provider: dict, messages: list[dict], timeout: float) -> str:
    body = json.dumps({
        "model": provider["model"],
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(provider["url"], data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider['key']}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def chat_json(system: str, user: str, required_keys: list[str], trace=None,
              attempts: int = 4, timeout: float = 45.0) -> dict:
    """Ask for a JSON object with required_keys. Retries rate limits and server errors with
    exponential backoff, asks once for a repair on a bad reply, then falls to the next
    provider. Raises LLMError when every provider fails."""
    errors = []
    for provider in _providers():
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        repaired = False
        for attempt in range(attempts):
            try:
                content = _post(provider, messages, timeout)
                parsed = json.loads(content)
                missing = [k for k in required_keys if k not in parsed]
                if missing:
                    raise ValueError(f"reply is missing keys {missing}")
                if trace:
                    trace.log("llm.call", provider=provider["name"], model=provider["model"], ok=True)
                return parsed
            except urllib.error.HTTPError as e:
                errors.append(f"{provider['name']}: HTTP {e.code}")
                if e.code not in RETRY_STATUS:
                    break
                retry_after = e.headers.get("retry-after") if e.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(min(delay, 20) + random.random())
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                errors.append(f"{provider['name']}: bad reply ({e})")
                if repaired:
                    break
                repaired = True
                messages.append({"role": "user", "content":
                                 f"Your reply was not valid. Reply with one JSON object only, with keys {required_keys}."})
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                errors.append(f"{provider['name']}: {type(e).__name__}")
                time.sleep(2 ** attempt)
        if trace:
            trace.log("llm.call", provider=provider["name"], ok=False, errors=errors[-3:])
    raise LLMError("; ".join(errors) or "no LLM provider configured")
