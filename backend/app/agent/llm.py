import os

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()


def get_llm():
    """
    Create the configured debugging LLM.
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. "
            "Add it to backend/.env"
        )

    model_name = os.getenv(
        "LLM_MODEL",
        "openrouter/free",
    )

    return ChatOpenRouter(
        model=model_name,
        temperature=0.2,
        max_tokens=2048,
    )