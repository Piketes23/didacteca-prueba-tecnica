import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.conflicts import detect_conflicts
from src.context_client import fetch_context
from src.errors import AppError
from src.generator import run_action
from src.schemas import ErrorResponse, ExecuteRequest

logger = logging.getLogger("didacteca")

SUPPORTED_ACTIONS = ("chat", "quiz", "activity")

app = FastAPI(title="Didacteca - Prueba técnica AI Engineer Jr")


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_request(req: ExecuteRequest) -> tuple[str, str, str, str]:
    action = _text(req.action).lower()
    book_id = _text(req.book_id)
    section_id = _text(req.section_id)
    instructions = _text(req.instructions)

    if action and action not in SUPPORTED_ACTIONS:
        raise AppError(
            "UNSUPPORTED_ACTION",
            f"La acción '{req.action}' no está soportada. Usa: chat, quiz o activity.",
            400,
            details={"supported_actions": list(SUPPORTED_ACTIONS)},
        )

    missing = []
    if not action:
        missing.append("action")
    if not book_id:
        missing.append("book_id")
    if not section_id:
        missing.append("section_id")
    if action == "chat" and not instructions:
        missing.append("instructions")

    if missing:
        raise AppError(
            "MISSING_FIELDS",
            "Faltan datos obligatorios: "
            + ", ".join(missing)
            + ". Envía la solicitud completa. (Para chat, 'instructions' es la pregunta.)",
            422,
            status="needs_clarification",
            missing_fields=missing,
        )

    conflicts = detect_conflicts(action, instructions)
    if conflicts:
        raise AppError(
            "AMBIGUOUS_INSTRUCTIONS",
            "Las instrucciones se contradicen: "
            + "; ".join(conflicts)
            + ". Envía una versión con un solo valor.",
            422,
            status="needs_clarification",
            details={"conflicts": conflicts},
        )

    return action, book_id, section_id, instructions


def _error_response(exc: AppError) -> JSONResponse:
    body = ErrorResponse(
        status=exc.status,
        code=exc.code,
        message=exc.message,
        missing_fields=exc.missing_fields,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump())


@app.post("/execute")
async def execute(req: ExecuteRequest):
    action, book_id, section_id, instructions = validate_request(req)
    context = await fetch_context(book_id, section_id)
    result = await run_action(action, context, instructions)
    return JSONResponse(content=result.model_dump(exclude_none=True))


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return _error_response(exc)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request: Request, exc: RequestValidationError):
    problems = [
        {
            "field": ".".join(str(p) for p in e["loc"] if p != "body"),
            "problem": e["msg"],
        }
        for e in exc.errors()
    ]
    return _error_response(
        AppError(
            "INVALID_REQUEST",
            "La solicitud no tiene el formato esperado: envía un JSON cuyos campos "
            "(action, book_id, section_id, instructions) sean texto.",
            422,
            details={"errors": problems},
        )
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Error inesperado")
    return _error_response(
        AppError("INTERNAL_ERROR", "Ocurrió un error inesperado en el servidor.", 500)
    )