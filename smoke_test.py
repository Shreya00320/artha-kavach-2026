"""Smoke test script for Artha Kavach LLM adapter.

Makes a single minimal call to verify real LLM connectivity using credentials
configured in the environment / .env file, parses the output against a Pydantic
schema, and prints the validated JSON result.
"""

import sys
from dotenv import load_dotenv

from llm.adapter import LLMAdapter, LLMAdapterError, LLMConfigurationError
from llm.schemas import SmokeTestResult

# Load environment configuration (.env)
load_dotenv()


def run_smoke_test() -> int:
    """Execute smoke test and print structured JSON response."""
    print("=" * 60)
    print("Artha Kavach — Phase 0 LLM Adapter Smoke Test")
    print("=" * 60)

    try:
        adapter = LLMAdapter()
    except LLMConfigurationError as e:
        print(f"\n[CONFIGURATION ERROR] {e}")
        print("\nPlease check that your .env file defines:")
        print("  LLM_PROVIDER=groq            (or gemini)")
        print("  GROQ_API_KEY=<your-groq-key>  (or GEMINI_API_KEY for gemini)")
        print("  LLM_MODEL=openai/gpt-oss-120b (or a current Gemini Flash id)")
        return 1

    print(f"Provider : {adapter.provider}")
    print(f"Model    : {adapter.model}")
    print(f"Cache    : {'Enabled (' + str(adapter.cache_dir) + ')' if adapter.cache_enabled else 'Disabled'}")
    print("-" * 60)
    print("Sending smoke test request...")

    prompt = (
        "Respond with a short JSON confirmation: "
        "status must be 'ok', "
        "message must be 'Artha Kavach Phase 0 smoke test successful', "
        "and provide the current timestamp or 'live-test'."
    )

    try:
        result = adapter.generate_structured(prompt=prompt, response_model=SmokeTestResult)
        print("-" * 60)
        print("Smoke Test Response Received & Validated:")
        print(result.model_dump_json(indent=2))
        print("-" * 60)
        print("RESULT: SMOKE TEST PASSED (Status: OK)")
        print("=" * 60)
        return 0

    except LLMAdapterError as e:
        print(f"\n[ADAPTER ERROR] {e}")
        return 2
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")
        return 3


if __name__ == "__main__":
    sys.exit(run_smoke_test())
