"""Ollama client for local LLM inference."""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Timeouts
CONNECT_TIMEOUT = 10.0  # seconds
READ_TIMEOUT = 120.0  # seconds for streaming responses
GENERATE_TIMEOUT = 300.0  # 5 minutes max for full generation


class OllamaError(Exception):
    """Base exception for Ollama errors."""

    pass


class OllamaConnectionError(OllamaError):
    """Raised when unable to connect to Ollama."""

    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request times out."""

    pass


class OllamaModelError(OllamaError):
    """Raised when model is not available."""

    pass


@dataclass
class OllamaResponse:
    """Response from Ollama generate endpoint."""

    response: str
    model: str
    done: bool
    total_duration: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


async def check_ollama_health() -> bool:
    """Check if Ollama is running and accessible.

    Returns:
        True if Ollama is healthy, False otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        return False


async def check_model_available(model: str | None = None) -> bool:
    """Check if the specified model is available in Ollama.

    Args:
        model: Model name to check. Defaults to configured model.

    Returns:
        True if model is available, False otherwise.
    """
    model = model or settings.ollama_model
    try:
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code != 200:
                return False

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            # Check for exact match or match without tag
            for available_model in models:
                if available_model == model or available_model.startswith(f"{model}:"):
                    return True

            return False
    except Exception as e:
        logger.warning(f"Model availability check failed: {e}")
        return False


async def generate(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> OllamaResponse:
    """Generate a response from Ollama (non-streaming).

    Args:
        prompt: The prompt to send.
        model: Model to use. Defaults to configured model.
        system: System prompt.
        temperature: Sampling temperature (0-1).
        max_tokens: Maximum tokens to generate.

    Returns:
        OllamaResponse with the generated text.

    Raises:
        OllamaConnectionError: If unable to connect to Ollama.
        OllamaTimeoutError: If request times out.
        OllamaModelError: If model is not available.
    """
    model = model or settings.ollama_model

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    if system:
        payload["system"] = system

    if max_tokens:
        payload["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=GENERATE_TIMEOUT)
        ) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )

            if response.status_code == 404:
                raise OllamaModelError(f"Model '{model}' not found")

            response.raise_for_status()
            data = response.json()

            return OllamaResponse(
                response=data.get("response", ""),
                model=data.get("model", model),
                done=data.get("done", True),
                total_duration=data.get("total_duration"),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )

    except httpx.ConnectError as e:
        raise OllamaConnectionError(
            f"Failed to connect to Ollama at {settings.ollama_base_url}: {e}"
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaTimeoutError(f"Ollama request timed out: {e}") from e
    except httpx.HTTPStatusError as e:
        raise OllamaError(f"Ollama HTTP error: {e}") from e


async def generate_stream(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Generate a streaming response from Ollama.

    Args:
        prompt: The prompt to send.
        model: Model to use. Defaults to configured model.
        system: System prompt.
        temperature: Sampling temperature (0-1).
        max_tokens: Maximum tokens to generate.

    Yields:
        Token strings as they are generated.

    Raises:
        OllamaConnectionError: If unable to connect to Ollama.
        OllamaTimeoutError: If request times out.
        OllamaModelError: If model is not available.
    """
    model = model or settings.ollama_model

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
        },
    }

    if system:
        payload["system"] = system

    if max_tokens:
        payload["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT)
        ) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            ) as response:
                if response.status_code == 404:
                    raise OllamaModelError(f"Model '{model}' not found")

                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token

                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse Ollama response: {line}")
                        continue

    except httpx.ConnectError as e:
        raise OllamaConnectionError(
            f"Failed to connect to Ollama at {settings.ollama_base_url}: {e}"
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaTimeoutError(f"Ollama request timed out: {e}") from e
    except httpx.HTTPStatusError as e:
        raise OllamaError(f"Ollama HTTP error: {e}") from e
