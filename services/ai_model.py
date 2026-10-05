from langchain_openai import ChatOpenAI

from config.settings import get_settings
from contracts.agent_result import AgentPlanProposal


def get_ai_model(
    *,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
) -> ChatOpenAI:
    settings = get_settings()

    api_key = (
        settings.ai_api_key
        .get_secret_value()
        .strip()
    )

    if not api_key:
        raise RuntimeError(
            "SCHEMABRIDGE_AI_API_KEY is not configured."
        )

    return ChatOpenAI(
        model=settings.ai_model,
        base_url=settings.ai_base_url,
        api_key=api_key,
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_output_tokens,
        timeout=timeout_seconds or settings.ai_timeout_seconds,
        max_retries=(
            settings.ai_max_retries if max_retries is None else max_retries
        ),
    )


def get_proposal_model(
    *,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
    structured_method: str | None = None,
):
    settings = get_settings()
    method = structured_method or settings.ai_structured_method
    model = get_ai_model(
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

    return model.with_structured_output(
        AgentPlanProposal,
        method=method,
        strict=True if method == "json_schema" else None,
    )
