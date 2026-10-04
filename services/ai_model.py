from langchain_openai import ChatOpenAI

from config.settings import get_settings
from contracts.agent_result import AgentPlanProposal


def get_ai_model() -> ChatOpenAI:
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
        timeout=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )


def get_proposal_model():
    model = get_ai_model()

    return model.with_structured_output(
        AgentPlanProposal,
        method="json_schema",
        strict=True,
    )
