from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_run import AgentQuestion, AgentRun


async def create_agent_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
    source_schema_id: UUID,
    target_schema_id: UUID,
    model_name: str,
    prompt_version: str,
    rule_list_version: str,
    created_by: str,
) -> AgentRun:
    run = AgentRun(
        project_id=project_id,
        dataset_id=dataset_id,
        source_schema_id=source_schema_id,
        target_schema_id=target_schema_id,
        model_name=model_name,
        prompt_version=prompt_version,
        rule_list_version=rule_list_version,
        created_by=created_by,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def get_agent_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
) -> AgentRun | None:
    result = await session.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def save_agent_result(
    session: AsyncSession,
    *,
    run: AgentRun,
    result: dict,
) -> AgentRun:
    if "proposal" in result:
        run.proposal = result["proposal"]
    if "validation" in result:
        run.validation = result["validation"]
    if "preview" in result:
        run.preview = result["preview"]
    if "target_conflicts" in result:
        run.target_conflicts = result["target_conflicts"]
    if "tool_evidence" in result:
        run.tool_evidence = result["tool_evidence"]
    if "transcript_metadata" in result:
        run.transcript_metadata = result["transcript_metadata"]
    if "failure_reason" in result:
        run.failure_reason = result["failure_reason"]
    run.revision_count = result.get("revision_count", run.revision_count)
    run.status = result.get("status", run.status)
    if run.status in {"ready_for_review", "invalid", "failed"}:
        run.completed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(run)
    return run


async def store_questions(
    session: AsyncSession,
    *,
    run_id: UUID,
    revision_number: int,
    questions: list[dict],
) -> list[AgentQuestion]:
    existing = await list_agent_questions(
        session,
        run_id=run_id,
        revision_number=revision_number,
    )
    if existing:
        return list(existing)

    stored: list[AgentQuestion] = []
    for number, item in enumerate(questions, start=1):
        question = AgentQuestion(
            agent_run_id=run_id,
            revision_number=revision_number,
            question_number=number,
            question=item["question"],
            reason=item["reason"],
            affected_fields=item.get("affected_fields", []),
            blocking=item.get("blocking", True),
        )
        session.add(question)
        stored.append(question)
    await session.flush()
    for question in stored:
        await session.refresh(question)
    return stored


async def list_agent_questions(
    session: AsyncSession,
    *,
    run_id: UUID,
    revision_number: int | None = None,
) -> Sequence[AgentQuestion]:
    query = select(AgentQuestion).where(AgentQuestion.agent_run_id == run_id)
    if revision_number is not None:
        query = query.where(AgentQuestion.revision_number == revision_number)
    result = await session.execute(
        query.order_by(
            AgentQuestion.revision_number,
            AgentQuestion.question_number,
        )
    )
    return result.scalars().all()


async def get_agent_question(
    session: AsyncSession,
    *,
    run_id: UUID,
    question_id: UUID,
) -> AgentQuestion | None:
    result = await session.execute(
        select(AgentQuestion).where(
            AgentQuestion.id == question_id,
            AgentQuestion.agent_run_id == run_id,
        )
    )
    return result.scalar_one_or_none()


async def save_answer(
    session: AsyncSession,
    *,
    question: AgentQuestion,
    answer: str,
    actor_id: str,
) -> AgentQuestion:
    question.answer = answer
    question.answered_by = actor_id
    question.answered_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(question)
    return question
