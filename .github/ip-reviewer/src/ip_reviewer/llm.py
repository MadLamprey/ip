"""LLM dispatch.

The reviewer talks to one of several LLM providers behind a single
`chat()` / `chat_json()` API. Pick the provider with `IP_REVIEWER_PROVIDER`
(default `groq`); override the model with `IP_REVIEWER_MODEL`; provide the
provider's API key in its own env var.

Adding a new provider should mean: register defaults in `_PROVIDERS`, write a
small client constructor, and you're done. The Groq and OpenAI SDKs both use
the OpenAI-compatible `client.chat.completions.create(...)` shape, so the
call site is provider-agnostic past `_client()`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable

DEFAULT_PROVIDER = "groq"
DEFAULT_TEMPERATURE = 0.2
JSON_TEMPERATURE = 0.1

_PROVIDERS = {
    "groq": {
        "model": "llama-3.1-8b-instant",
        "key_env": "GROQ_API_KEY",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
}


def _provider() -> str:
    raw = (os.environ.get("IP_REVIEWER_PROVIDER") or "").strip().lower()
    name = raw or DEFAULT_PROVIDER
    if name not in _PROVIDERS:
        raise RuntimeError(
            f"Unsupported IP_REVIEWER_PROVIDER={name!r}. "
            f"Known: {', '.join(sorted(_PROVIDERS))}."
        )
    return name


def _model() -> str:
    explicit = (os.environ.get("IP_REVIEWER_MODEL") or "").strip()
    if explicit:
        return explicit
    return _PROVIDERS[_provider()]["model"]


def _api_key() -> str:
    var = _PROVIDERS[_provider()]["key_env"]
    key = os.environ.get(var)
    if not key:
        raise RuntimeError(f"{var} is not set")
    return key


def _client():
    name = _provider()
    if name == "groq":
        from groq import Groq

        return Groq(api_key=_api_key())
    if name == "openai":
        from openai import OpenAI

        return OpenAI(api_key=_api_key())
    raise RuntimeError(f"Unsupported provider: {name}")


def chat(
    messages: Iterable[dict],
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    response_format: dict | None = None,
) -> str:
    """Send a chat completion and return the model's text reply."""
    kwargs = {
        "model": _model(),
        "temperature": temperature,
        "messages": list(messages),
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    response = _client().chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def chat_json(messages: Iterable[dict], *, temperature: float = JSON_TEMPERATURE):
    """Like chat(), but constrain output to JSON and parse it.

    Both Groq and OpenAI support `response_format={"type": "json_object"}`,
    which constrains the model to emit valid JSON. The caller is responsible
    for asking for an object (the format does not allow a bare array). We
    fall back to permissive regex extraction if for some reason the response
    still isn't strict JSON.
    """
    raw = chat(
        messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return JSON. Got: {raw[:300]!r}")

    return json.loads(match.group(1))


def truncate(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[truncated]"
