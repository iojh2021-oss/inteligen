import os
import httpx

class ModelUnavailable(RuntimeError):
    pass

async def generate(system_prompt: str, user_prompt: str) -> str:
    base = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    model = os.getenv("MODEL_NAME", "qwen3:4b")
    key = os.getenv("MODEL_API_KEY", "")
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise ModelUnavailable(f"Model endpoint unavailable or returned an invalid response: {exc}") from exc
