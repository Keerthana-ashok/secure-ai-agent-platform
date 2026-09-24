"""Simple experiment: call the LLM with different temperatures and token limits.

This version is written for beginners with clear steps and short comments.

Run with:
  export LLM_API_KEY="your_key"
  python scripts/temperature_experiment.py
"""

import asyncio
from app.llm.client import LLMClient
from app.config import get_settings


async def main():
    # Load settings (from environment or .env)
    settings = get_settings()

    # Create a client to talk to the LLM provider
    client = LLMClient(settings=settings)

    # The question we will send to the model
    prompt = "Explain authentication in simple terms."

    # Values we'll try for temperature and max tokens
    temperatures = [0.0, 0.5, 1.0]
    max_tokens_values = [50, 150]

    # Loop over each combination and print the model's reply
    for temp in temperatures:
        for max_t in max_tokens_values:
            print(f"\n--- temperature={temp}  max_tokens={max_t} ---")
            messages = [{"role": "user", "content": prompt}]
            try:
                # Call the LLM. We pass temperature and max_tokens to override defaults.
                answer = await client.send_prompt(messages, temperature=temp, max_tokens=max_t)
                print(answer)
            except Exception as e:
                print("Error calling LLM:", e)

    # Close the underlying HTTP client
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
