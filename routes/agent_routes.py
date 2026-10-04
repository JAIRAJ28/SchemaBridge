from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from contracts.agent_run import (
    AgentAnswer,
    AgentQuestionResponse,
    AgentRunResponse,
    AgentRunStart,
)
from routes.route_helpers import ActorId, DatabaseSession, get_request_id
from services.agent_actions import (
    answer_agent_question,
    get_agent_run_service,
    list_agent_questions_service,
    resume_agent_run,
    start_agent_run,
)


router = APIRouter(prefix="/projects/{project_id}/agent-runs", tags=["agent"])


@router.post("", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def start_agent_route(
    project_id: UUID,
    body: AgentRunStart,
    actor_id: ActorId,
    session: DatabaseSession,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> AgentRunResponse:
    run = await start_agent_run(
        session,
        project_id=project_id,
        actor_id=actor_id,
        request_id=request_id,
        request=body,
        checkpointer=request.app.state.checkpointer,
    )
    return AgentRunResponse.model_validate(run)


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> AgentRunResponse:
    run = await get_agent_run_service(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )
    return AgentRunResponse.model_validate(run)


@router.get("/{run_id}/questions", response_model=list[AgentQuestionResponse])
async def list_questions_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> list[AgentQuestionResponse]:
    questions = await list_agent_questions_service(
        session, project_id=project_id, run_id=run_id, actor_id=actor_id
    )
    return [AgentQuestionResponse.model_validate(item) for item in questions]


@router.post(
    "/{run_id}/questions/{question_id}/answer",
    response_model=AgentQuestionResponse,
)
async def answer_question_route(
    project_id: UUID,
    run_id: UUID,
    question_id: UUID,
    body: AgentAnswer,
    actor_id: ActorId,
    session: DatabaseSession,
) -> AgentQuestionResponse:
    question = await answer_agent_question(
        session,
        project_id=project_id,
        run_id=run_id,
        question_id=question_id,
        actor_id=actor_id,
        answer=body.answer,
    )
    return AgentQuestionResponse.model_validate(question)


@router.post("/{run_id}/resume", response_model=AgentRunResponse)
async def resume_agent_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> AgentRunResponse:
    run = await resume_agent_run(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
        request_id=request_id,
        checkpointer=request.app.state.checkpointer,
    )
    return AgentRunResponse.model_validate(run)
