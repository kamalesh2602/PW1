import os

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()


def get_model_name() -> str:
    """
    Get the configured or inferred LLM model name.
    """
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""
    model_name = os.getenv("LLM_MODEL", "openrouter/free")
    if api_key.startswith("gsk_") or os.getenv("GROQ_API_KEY"):
        if "openrouter" in model_name:
            return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    return model_name


class DebugChatModel(ChatOpenRouter):
    """
    OpenRouter chat model subclass that defaults structured output to 'json_schema'
    for robust compatibility with Groq and OpenAI-compatible structured outputs.
    """
    def with_structured_output(self, schema=None, *, method="json_schema", **kwargs):
        return super().with_structured_output(schema, method=method, **kwargs)


def get_llm():
    """
    Create the configured debugging LLM.
    Supports OpenRouter as well as Groq API keys seamlessly.
    """

    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY or GROQ_API_KEY is not configured. "
            "Add it to backend/.env"
        )

    model_name = os.getenv(
        "LLM_MODEL",
        "openrouter/free",
    )

    kwargs = {
        "temperature": 0.2,
        "max_tokens": 2048,
        "stream_usage": True,
    }

    # If key starts with gsk_ or GROQ_API_KEY is set, route to Groq API
    if api_key.startswith("gsk_") or os.getenv("GROQ_API_KEY"):
        kwargs["openrouter_api_base"] = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        kwargs["openrouter_api_key"] = api_key
        if "openrouter" in model_name:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        kwargs["model"] = model_name
        return DebugChatModel(**kwargs)
    else:
        kwargs["api_key"] = api_key
        kwargs["model"] = model_name
        return ChatOpenRouter(**kwargs)