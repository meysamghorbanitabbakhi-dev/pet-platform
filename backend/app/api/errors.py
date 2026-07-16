from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc.detail, str):
        code = exc.detail.lower().replace(" ", "_")
        message = exc.detail if " " in exc.detail else exc.detail.replace("_", " ")
        details = None
    else:
        code, message, details = "http_error", "Request could not be completed", exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(request, code=code, message=message, details=details),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details = [
        {
            "location": [str(part) for part in item["loc"]],
            "message": item["msg"],
            "type": item["type"],
        }
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_payload(
            request,
            code="validation_error",
            message="Request validation failed",
            details=details,
        ),
    )
