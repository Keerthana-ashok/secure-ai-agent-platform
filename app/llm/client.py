import httpx
from typing import List, Dict, Optional

from ..config import get_settings, Settings


class LLMError(Exception):
    """Raised when the LLM client encounters a problem."""


class LLMClient:
    """Readable, beginner-friendly async LLM client.

    This version favors clarity over advanced patterns. It:
    - constructs the HTTP client in `__init__`,
    - uses straightforward variable names and short comments,
    - supports per-call overrides for `temperature`, `max_tokens`, and `model`.
    """

    def __init__(self, settings: Optional[Settings] = None):
        # Load configuration (API key, defaults) from Settings
        self.settings = settings or get_settings()

        # Create an AsyncClient once and reuse it. This keeps code simple.
        # The timeout here is the default; per-call timeouts are not used in this simpler variant.
        self.client = httpx.AsyncClient(timeout=self.settings.timeout)

    async def send_prompt(
        self,
        messages: List[Dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Send messages to the LLM and return the text response.

        messages: list like [{"role":"user","content":"..."}]
        temperature/max_tokens/model: optional overrides for this call
        """

        # Ensure API key is present
        if not self.settings.llm_api_key:
            raise LLMError("LLM API key not configured. Set LLM_API_KEY in your environment.")

        # Build the request body using either provided overrides or defaults
        body = {
            "model": model or self.settings.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.settings.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.settings.max_tokens,
        }

        # Authorization header with the API key from settings
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}

        try:
            # Send the POST request to the provider URL
            response = await self.client.post(self.settings.provider_url, json=body, headers=headers)

            # Raise for HTTP errors (4xx, 5xx)
            response.raise_for_status()

            # Try to decode JSON. If the provider returns plain text, return that.
            try:
                data = response.json()
            except ValueError:
                return response.text

            # Common response shapes: {"response": "..."} or {"choices": [{"text": "..."}]}
            if isinstance(data, dict):
                if "response" in data:
                    return data["response"]
                if "choices" in data and data["choices"]:
                    first = data["choices"][0]
                    # return text, or message.content, or string representation
                    return first.get("text") or (first.get("message") or {}).get("content") or str(first)

            # Fallback: stringify whatever we got
            return str(data)

        except httpx.TimeoutException:
            raise LLMError("LLM request timed out")
        except httpx.HTTPStatusError as e:
            # Keep the error simple and readable
            status = e.response.status_code
            text = e.response.text[:200]
            raise LLMError(f"LLM API error {status}: {text}")
        except httpx.RequestError as e:
            raise LLMError(f"Network error when calling LLM: {e}")

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Call this when the program finishes."""
        await self.client.aclose()

