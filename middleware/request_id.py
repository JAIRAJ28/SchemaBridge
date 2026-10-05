import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
logger = logging.getLogger("schemabridge.requests")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


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
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        if request.url.path != "/health":
            logger.info(json.dumps({
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            }))
