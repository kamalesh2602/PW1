"""
Token usage tracking and extraction for LangChain and OpenRouter models.
Provides a normalized token extraction path for provider responses (AIMessage, LLMResult, ChatResult, dict).
Distinguishes between actual token usage (including 0) and missing/unavailable metadata.
"""

from dataclasses import dataclass
from typing import Any, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


@dataclass
class TokenUsageResult:
    """
    Normalized token usage extracted from an LLM response.
    """
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "available": self.available,
        }


def extract_token_usage(response: Any) -> TokenUsageResult:
    """
    Normalized token usage extraction path for OpenRouter and LangChain responses.
    Inspects response objects (AIMessage, LLMResult, ChatResult, dict, etc.)
    for actual provider usage metadata.

    Returns TokenUsageResult:
    - If provider usage metadata exists: input_tokens, output_tokens, total_tokens, available=True
    - If usage metadata is genuinely missing: input_tokens=None, output_tokens=None, total_tokens=None, available=False
    Never estimates or converts missing values to 0.
    """
    if response is None:
        return TokenUsageResult(available=False)

    found_input: Optional[int] = None
    found_output: Optional[int] = None
    found_total: Optional[int] = None
    available = False

    def _extract_from_dict(d: dict[str, Any]) -> bool:
        nonlocal found_input, found_output, found_total, available
        if not isinstance(d, dict):
            return False

        # 1. Check nested usage dictionaries
        for nested_key in ("usage_metadata", "usage", "token_usage"):
            nested = d.get(nested_key)
            if isinstance(nested, dict):
                if _extract_from_dict(nested):
                    return True

        # 2. Check response_metadata nested dict
        rm = d.get("response_metadata")
        if isinstance(rm, dict):
            if _extract_from_dict(rm):
                return True

        # 3. Direct token fields (OpenRouter & OpenAI format)
        in_val = d.get("input_tokens") if d.get("input_tokens") is not None else d.get("prompt_tokens")
        out_val = d.get("output_tokens") if d.get("output_tokens") is not None else d.get("completion_tokens")
        tot_val = d.get("total_tokens")

        if in_val is not None or out_val is not None or tot_val is not None:
            inp = int(in_val) if in_val is not None else 0
            out = int(out_val) if out_val is not None else 0
            tot = int(tot_val) if tot_val is not None else (inp + out)
            found_input = inp
            found_output = out
            found_total = tot
            available = True
            return True

        return False

    # 1. If response is LLMResult (LangChain callback response)
    if isinstance(response, LLMResult) or hasattr(response, "generations"):
        total_inp = 0
        total_out = 0
        total_tot = 0
        any_found = False

        generations = getattr(response, "generations", [])
        if generations:
            for gen_item in generations:
                gen_list = gen_item if isinstance(gen_item, list) else [gen_item]
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg:
                        sub_res = extract_token_usage(msg)
                        if sub_res.available:
                            any_found = True
                            total_inp += sub_res.input_tokens or 0
                            total_out += sub_res.output_tokens or 0
                            total_tot += sub_res.total_tokens or 0

        # Fallback to LLMResult.llm_output
        llm_out = getattr(response, "llm_output", None)
        if not any_found and isinstance(llm_out, dict):
            fallback_res = extract_token_usage(llm_out)
            if fallback_res.available:
                return fallback_res

        if any_found:
            return TokenUsageResult(
                input_tokens=total_inp,
                output_tokens=total_out,
                total_tokens=total_tot if total_tot > 0 else (total_inp + total_out),
                available=True,
            )

    # 2. If response is AIMessage or object with usage_metadata attribute
    um = getattr(response, "usage_metadata", None)
    if isinstance(um, dict) and _extract_from_dict(um):
        return TokenUsageResult(
            input_tokens=found_input,
            output_tokens=found_output,
            total_tokens=found_total,
            available=True,
        )

    # 3. Check response_metadata attribute (AIMessage / ChatGeneration)
    rm = getattr(response, "response_metadata", None)
    if isinstance(rm, dict) and _extract_from_dict(rm):
        return TokenUsageResult(
            input_tokens=found_input,
            output_tokens=found_output,
            total_tokens=found_total,
            available=True,
        )

    # 4. If response is a dict directly
    if isinstance(response, dict) and _extract_from_dict(response):
        return TokenUsageResult(
            input_tokens=found_input,
            output_tokens=found_output,
            total_tokens=found_total,
            available=True,
        )

    # 5. Check object.telemetry if available
    telemetry = getattr(response, "telemetry", None)
    if isinstance(telemetry, dict) and telemetry.get("token_usage_available"):
        return TokenUsageResult(
            input_tokens=telemetry.get("input_tokens"),
            output_tokens=telemetry.get("output_tokens"),
            total_tokens=telemetry.get("total_tokens"),
            available=True,
        )

    return TokenUsageResult(
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        available=False,
    )


class TokenUsageCallback(BaseCallbackHandler):
    """
    Thread-safe callback handler to capture exact input, output,
    and total token usage metadata directly from the LLM provider.
    Uses the normalized extract_token_usage() path.
    """

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self.calls: int = 0
        self.records: list[dict[str, Any]] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.calls += 1
        res = extract_token_usage(response)

        if res.available:
            call_input = res.input_tokens or 0
            call_output = res.output_tokens or 0
            call_total = res.total_tokens or (call_input + call_output)

            self.input_tokens += call_input
            self.output_tokens += call_output
            self.total_tokens += call_total
        else:
            call_input = None
            call_output = None
            call_total = None

        self.records.append({
            "call_index": self.calls,
            "input_tokens": call_input,
            "output_tokens": call_output,
            "total_tokens": call_total,
            "available": res.available,
        })

    @property
    def usage_available(self) -> bool:
        """True only if at least one call was made and all calls recorded valid provider usage."""
        if self.calls == 0:
            return False
        return len(self.records) == self.calls and all(r.get("available", False) for r in self.records)

    @property
    def safe_input_tokens(self) -> Optional[int]:
        return self.input_tokens if self.usage_available else None

    @property
    def safe_output_tokens(self) -> Optional[int]:
        return self.output_tokens if self.usage_available else None

    @property
    def safe_total_tokens(self) -> Optional[int]:
        return self.total_tokens if self.usage_available else None

    def reset(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.records = []
