"""Model adapter: one small interface in front of any OpenAI-compatible local server
(Ollama, llama.cpp server, LM Studio, vLLM...). Swap models by changing .env only."""
import re
from typing import Optional, Protocol

import httpx

from app import config


class ModelUnavailable(RuntimeError):
    pass


class ModelClient(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...
    async def ping(self) -> bool: ...


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


def clean_output(text: str) -> str:
    """Remove reasoning traces (Qwen3 and similar emit <think>...</think>)."""
    text = _THINK_BLOCK.sub("", text)
    text = _THINK_OPEN.sub("", text)  # unterminated block (truncated output)
    return text.strip()


class OpenAICompatibleClient:
    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._transport = transport  # injectable for tests

    def _headers(self) -> dict:
        key = config.model_api_key()
        return {"Authorization": f"Bearer {key}"} if key else {}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=config.request_timeout(), transport=self._transport)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": config.model_name(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
        }
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{config.model_base_url()}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise ModelUnavailable(
                f"Model endpoint unavailable or returned an invalid response: {exc}"
            ) from exc
        text = clean_output(content or "")
        if not text:
            raise ModelUnavailable("Model returned an empty answer.")
        return text

    async def ping(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{config.model_base_url()}/models", headers=self._headers()
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False


_client: ModelClient = OpenAICompatibleClient()


def get_client() -> ModelClient:
    return _client


def set_client(client: ModelClient) -> None:
    """Replace the active client (used by tests and future model routing)."""
    global _client
    _client = client


async def generate(system_prompt: str, user_prompt: str) -> str:
    return await _client.generate(system_prompt, user_prompt)
