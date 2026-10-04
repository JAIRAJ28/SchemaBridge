from uuid import UUID

from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from config.settings import get_settings
from contracts.agent_run import AgentRunStart
from contracts.plan import PlanCreate
from middleware.error_handler import ApplicationError
from models.agent_run import AgentRun
from repositories.agent_db import (
    create_agent_run,
    get_agent_question,
    get_agent_run,
    list_agent_questions,
    save_agent_result,
    save_answer,
    store_questions,
)
from repositories.project_db import get_project_by_id
from services.agent_flow import build_agent_graph
from services.agent_tools import AgentToolContext, AgentTools
from services.plan_actions import create_plan_service
from services.rule_list import RULE_LIST_VERSION


async def _owned_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
) -> AgentRun:
    project = await get_project_by_id(session, project_id=project_id, owner_id=actor_id)
    run = await get_agent_run(session, project_id=project_id, run_id=run_id)
    if project is None or run is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Agent run was not found.",
            status_code=404,
        )
    return run


def _graph(
    *,
    session: AsyncSession,
    run: AgentRun,
    checkpointer: BaseCheckpointSaver,
    proposal_model: Runnable | None = None,
):
    tools = AgentTools(
        session=session,
        context=AgentToolContext(
            project_id=run.project_id,
            dataset_id=run.dataset_id,
            source_schema_id=run.source_schema_id,
            target_schema_id=run.target_schema_id,
        ),
    )
    return build_agent_graph(
        tools=tools,
        checkpointer=checkpointer,
        proposal_model=proposal_model,
    )


async def _save_graph_result(
    session: AsyncSession,
    *,
    run: AgentRun,
    result: dict,
    actor_id: str,
    request_id: str,
) -> AgentRun:
    interrupts = result.get("__interrupt__", ())
    if interrupts:
        payload = interrupts[0].value
        await store_questions(
            session,
            run_id=run.id,
            revision_number=payload["revision_number"],
            questions=payload["questions"],
        )
        result = dict(result)
        result["status"] = "needs_clarification"

    await save_agent_result(session, run=run, result=result)

    if run.status == "ready_for_review" and run.plan_id is None:
        plan = await create_plan_service(
            session,
            project_id=run.project_id,
            actor_id=actor_id,
            request_id=request_id,
            request=PlanCreate.model_validate(result["plan_data"]),
        )
        run.plan_id = plan.id

    await session.commit()
    await session.refresh(run)
    return run


async def start_agent_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    actor_id: str,
    request_id: str,
    request: AgentRunStart,
    checkpointer: BaseCheckpointSaver,
    proposal_model: Runnable | None = None,
) -> AgentRun:
    project = await get_project_by_id(session, project_id=project_id, owner_id=actor_id)
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )

    settings = get_settings()
    preflight_tools = AgentTools(
        session=session,
        context=AgentToolContext(
            project_id=project_id,
            dataset_id=request.dataset_id,
            source_schema_id=request.source_schema_id,
            target_schema_id=request.target_schema_id,
        ),
    )
    try:
        await preflight_tools.inspect_source_schema()
        await preflight_tools.inspect_target_schema()
        await preflight_tools.profile_source_dataset()
    except ValueError as error:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(error),
            status_code=422,
        ) from error

    run = await create_agent_run(
        session,
        project_id=project_id,
        dataset_id=request.dataset_id,
        source_schema_id=request.source_schema_id,
        target_schema_id=request.target_schema_id,
        model_name=settings.ai_model,
        prompt_version=settings.ai_prompt_version,
        rule_list_version=RULE_LIST_VERSION,
        created_by=actor_id,
    )
    await session.commit()

    graph = _graph(
        session=session,
        run=run,
        checkpointer=checkpointer,
        proposal_model=proposal_model,
    )
    config = {"configurable": {"thread_id": str(run.id)}}
    try:
        result = await graph.ainvoke({}, config=config)
        return await _save_graph_result(
            session,
            run=run,
            result=result,
            actor_id=actor_id,
            request_id=request_id,
        )
    except Exception as error:
        await session.rollback()
        run = await get_agent_run(session, project_id=project_id, run_id=run.id)
        if run is not None:
            await save_agent_result(
                session,
                run=run,
                result={
                    "status": "failed",
                    "failure_reason": (
                        f"{type(error).__name__}: {error}"
                    )[:1000],
                },
            )
            await session.commit()
        raise


async def get_agent_run_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
) -> AgentRun:
    return await _owned_run(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )


async def list_agent_questions_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
):
    await _owned_run(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )
    return await list_agent_questions(session, run_id=run_id)


async def answer_agent_question(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    question_id: UUID,
    actor_id: str,
    answer: str,
):
    run = await _owned_run(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )
    if run.status != "needs_clarification":
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="This agent run is not waiting for clarification.",
            status_code=409,
        )
    question = await get_agent_question(
        session, run_id=run_id, question_id=question_id
    )
    if question is None or question.revision_number != run.revision_count:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Agent question was not found.",
            status_code=404,
        )
    if question.answer is not None and question.answer != answer:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="This question has already been answered.",
            status_code=409,
        )
    if question.answer is None:
        await save_answer(
            session, question=question, answer=answer, actor_id=actor_id
        )
        await session.commit()
        await session.refresh(question)
    return question


async def resume_agent_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
    request_id: str,
    checkpointer: BaseCheckpointSaver,
    proposal_model: Runnable | None = None,
) -> AgentRun:
    run = await _owned_run(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )
    if run.status != "needs_clarification":
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="This agent run is not waiting for clarification.",
            status_code=409,
        )
    questions = await list_agent_questions(
        session, run_id=run_id, revision_number=run.revision_count
    )
    unanswered = [question for question in questions if question.blocking and not question.answer]
    if not questions or unanswered:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="Answer every blocking question before resuming the agent.",
            status_code=409,
        )
    answers = [
        {
            "question_id": str(question.id),
            "question": question.question,
            "answer": question.answer,
        }
        for question in questions
    ]
    graph = _graph(
        session=session,
        run=run,
        checkpointer=checkpointer,
        proposal_model=proposal_model,
    )
    config = {"configurable": {"thread_id": str(run.id)}}
    try:
        result = await graph.ainvoke(Command(resume={"answers": answers}), config=config)
        return await _save_graph_result(
            session,
            run=run,
            result=result,
            actor_id=actor_id,
            request_id=request_id,
        )
    except Exception as error:
        await session.rollback()
        run = await get_agent_run(session, project_id=project_id, run_id=run_id)
        if run is not None:
            await save_agent_result(
                session,
                run=run,
                result={
                    "status": "failed",
                    "failure_reason": (
                        f"{type(error).__name__}: {error}"
                    )[:1000],
                },
            )
            await session.commit()
        raise
