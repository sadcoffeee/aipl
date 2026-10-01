# Written by an LLM to speed up testing the inference server. Will be re-done for the final app.

from __future__ import annotations

import time
from typing import Any

import httpx

from . import config


class LLMError(Exception):
    """Something went wrong talking to the inference server."""


def _client(timeout: float | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=config.LLM_BASE_URL.rstrip("/"),
        timeout=timeout or config.LLM_TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )


def list_models() -> list[str]:
    """Model names the server currently offers."""
    try:
        with _client(timeout=10) as client:
            response = client.get("/models")
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach {config.LLM_BASE_URL}: {exc}") from exc
    return [entry.get("id", "") for entry in payload.get("data", [])]


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 512,
    response_format: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> str:
    """Send a conversation, get the reply text back.

    `messages` is the usual list of {"role": ..., "content": ...} entries.

    `response_format` is how to force structured output.
    """
    body: dict[str, Any] = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    if not body["model"]:
        raise LLMError("No model configured - set AIPL_LLM_MODEL in backend/.env")

    try:
        with _client(timeout) as client:
            response = client.post("/chat/completions", json=body)
            if response.status_code >= 400:
                raise LLMError(
                    f"The inference server returned {response.status_code}: "
                    f"{response.text[:400]}"
                )
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach {config.LLM_BASE_URL}: {exc}") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected reply shape: {str(payload)[:400]}") from exc


def check_connection() -> dict[str, Any]:
    """Can we reach the model, and does it answer?"""
    result: dict[str, Any] = {
        "baseUrl": config.LLM_BASE_URL,
        "configuredModel": config.LLM_MODEL or None,
        "reachable": False,
        "models": [],
        "modelAvailable": None,
        "reply": None,
        "latencyMs": None,
        "structuredOutput": None,
        "error": None,
    }

    try:
        result["models"] = list_models()
        result["reachable"] = True
    except LLMError as exc:
        result["error"] = str(exc)
        return result

    if config.LLM_MODEL:
        result["modelAvailable"] = config.LLM_MODEL in result["models"]
    elif len(result["models"]) == 1:
        # Only one model loaded: assume that is the one, so a missing
        # AIPL_LLM_MODEL does not stop the check being useful.
        result["configuredModel"] = result["models"][0]
        result["modelAvailable"] = True

    model = result["configuredModel"]
    if not model:
        result["error"] = (
            "Reachable, but no model configured. Set AIPL_LLM_MODEL to one of: "
            + ", ".join(result["models"])
        )
        return result

    started = time.perf_counter()
    try:
        result["reply"] = chat(
            [
                {
                    "role": "user",
                    "content": "Reply with exactly: connection ok",
                }
            ],
            model=model,
            max_tokens=20,
            timeout=60,
        )
        result["latencyMs"] = round((time.perf_counter() - started) * 1000)
    except LLMError as exc:
        result["error"] = str(exc)
        return result

    # Does this engine accept a JSON schema? 
    try:
        chat(
            [{"role": "user", "content": "Give me a random colour."}],
            model=model,
            max_tokens=40,
            timeout=60,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "colour",
                    "schema": {
                        "type": "object",
                        "properties": {"colour": {"type": "string"}},
                        "required": ["colour"],
                    },
                },
            },
        )
        result["structuredOutput"] = True
    except LLMError:
        result["structuredOutput"] = False

    return result