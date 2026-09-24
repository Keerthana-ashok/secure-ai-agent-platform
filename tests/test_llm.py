import pytest
import asyncio
from fastapi import HTTPException

from app.main import get_llm_client, chat_endpoint, ChatRequest
from app.config import get_settings, Settings
from app.llm.client import LLMError


class MockLLMClient:
    async def send_prompt(self, messages):
        return "Mocked response to: " + (messages[-1].get("content") if messages else "")


def override_get_llm_client():
    return MockLLMClient()


async def call_chat(message, conversation=None, llm_client=None):
    req = ChatRequest(message=message, conversation=conversation or [])
    try:
        return await chat_endpoint(req, llm=llm_client)
    except HTTPException as e:
        return e


def test_valid_prompt():
    llm = override_get_llm_client()
    res = asyncio.run(call_chat("Explain authentication", llm_client=llm))
    assert isinstance(res, dict)
    assert "response" in res


def test_empty_prompt_rejected():
    llm = override_get_llm_client()
    res = asyncio.run(call_chat("", llm_client=llm))
    assert isinstance(res, HTTPException)
    assert res.status_code == 400


def test_llm_response_returned():
    llm = override_get_llm_client()
    res = asyncio.run(call_chat("Hi", conversation=[{"role": "user", "content": "Hello"}], llm_client=llm))
    assert isinstance(res, dict)
    assert res["response"] == "Mocked response to: Hi"


def test_llm_api_failure_handled(monkeypatch):
    class FailingClient:
        async def send_prompt(self, messages):
            raise LLMError("provider down")

    llm = FailingClient()
    res = asyncio.run(call_chat("hello", llm_client=llm))
    assert isinstance(res, HTTPException)
    assert res.status_code == 503


def test_config_loaded_correctly(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    # clear cached settings
    from importlib import reload

    reload(__import__("app.config", fromlist=["*"]))
    s = get_settings()
    assert s.model_name == "test-model"


def test_api_key_not_hardcoded():
    s = Settings()
    assert s.llm_api_key is None
