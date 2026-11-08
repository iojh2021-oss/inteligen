import asyncio

import httpx
import pytest

from app import model


def run(coro):
    return asyncio.run(coro)


def client_with(handler):
    return model.OpenAICompatibleClient(transport=httpx.MockTransport(handler))


def ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_generate_returns_text_and_sends_openai_payload(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return ok("  hello  ")

    assert run(client_with(handler).generate("sys", "usr")) == "hello"
    assert seen["url"].endswith("/chat/completions")
    assert "test-model" in seen["body"] and "sys" in seen["body"] and "usr" in seen["body"]


def test_think_blocks_are_stripped():
    text = run(client_with(lambda r: ok("<think>secret reasoning</think>\nFinal answer")).generate("s", "u"))
    assert text == "Final answer"
    assert model.clean_output("<think>never closed") == ""


def test_http_error_becomes_model_unavailable():
    with pytest.raises(model.ModelUnavailable):
        run(client_with(lambda r: httpx.Response(500)).generate("s", "u"))


def test_malformed_response_becomes_model_unavailable():
    with pytest.raises(model.ModelUnavailable):
        run(client_with(lambda r: httpx.Response(200, json={"nope": 1})).generate("s", "u"))


def test_empty_answer_becomes_model_unavailable():
    with pytest.raises(model.ModelUnavailable):
        run(client_with(lambda r: ok("<think>only thinking</think>")).generate("s", "u"))


def test_ping():
    assert run(client_with(lambda r: httpx.Response(200, json={"data": []})).ping()) is True
    assert run(client_with(lambda r: httpx.Response(503)).ping()) is False
