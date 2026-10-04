import re
from uuid import uuid4

from fastapi import Request, Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


async def request_context_middleware(
    request: Request,
    call_next,
) -> Response:
    supplied_request_id = request.headers.get("X-Request-ID")
    if supplied_request_id and REQUEST_ID_PATTERN.fullmatch(supplied_request_id):
        request_id = supplied_request_id
    else:
        request_id = str(uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response
