"""Error type shared by every module, rendered as ``application/problem+json``."""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"

_CODE_BY_STATUS = {
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    429: "rate_limited",
}


class NovaError(Exception):
    """An expected failure with a stable ``code`` from the API contract."""

    def __init__(
        self,
        code: str,
        status: int,
        detail: str,
        *,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.status = status
        self.detail = detail
        self.extra = extra or {}
        self.headers = headers or {}


def request_id_of(request: Request) -> str | None:
    request_id: str | None = getattr(request.state, "request_id", None)
    return request_id


def problem(
    *,
    status: int,
    code: str,
    detail: str,
    request_id: str | None,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "code": code,
        "detail": detail,
        "request_id": request_id,
    }
    body.update(extra or {})
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=response_headers)


async def _render_nova_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NovaError)  # noqa: S101 - registered for NovaError only
    return problem(
        status=exc.status,
        code=exc.code,
        detail=exc.detail,
        request_id=request_id_of(request),
        extra=exc.extra,
        headers=exc.headers,
    )


async def _render_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = _CODE_BY_STATUS.get(
        exc.status_code, "internal_error" if exc.status_code >= 500 else "validation_error"
    )
    return problem(
        status=exc.status_code,
        code=code,
        detail=HTTPStatus(exc.status_code).phrase,
        request_id=request_id_of(request),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def _render_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    # Only loc, msg and type are returned: "input" and "ctx" could echo a password back.
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return problem(
        status=422,
        code="validation_error",
        detail="The request is invalid.",
        request_id=request_id_of(request),
        extra={"errors": errors},
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NovaError, _render_nova_error)
    app.add_exception_handler(StarletteHTTPException, _render_http_error)
    app.add_exception_handler(RequestValidationError, _render_validation_error)


class ProblemFieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class Problem(BaseModel):
    """Body of every error response, sent as ``application/problem+json``."""

    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    code: str
    detail: str
    request_id: str | None


class ValidationProblem(Problem):
    errors: list[ProblemFieldError]


def _problem_content(model: str) -> dict[str, Any]:
    return {PROBLEM_JSON: {"schema": {"$ref": f"#/components/schemas/{model}"}}}


def install_problem_schema(app: FastAPI) -> None:
    """Makes the OpenAPI schema describe the error bodies the server really sends.

    FastAPI documents its own validation error format, which this application replaces;
    client types generated from the schema would otherwise be wrong for every error.
    """
    generate = app.openapi
    rewritten = False

    def openapi() -> dict[str, Any]:
        nonlocal rewritten
        schema = generate()
        if rewritten:
            return schema
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (Problem, ValidationProblem):
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs", {}))
            components[model.__name__] = definition
        for name in ("HTTPValidationError", "ValidationError"):
            components.pop(name, None)
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                responses = operation.setdefault("responses", {})
                if "422" in responses:
                    responses["422"] = {
                        "description": "Validation error",
                        "content": _problem_content("ValidationProblem"),
                    }
                responses["default"] = {
                    "description": "Error",
                    "content": _problem_content("Problem"),
                }
        rewritten = True
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
