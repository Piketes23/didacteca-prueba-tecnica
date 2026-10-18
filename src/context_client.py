import httpx
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.errors import AppError


class SectionContext(BaseModel):
    book_id: str
    section_id: str
    title: str
    content: str


async def fetch_context(book_id: str, section_id: str) -> SectionContext:
    url = f"{settings.provided_service_base_url.rstrip('/')}/context"
    payload = {"book_id": book_id, "section_id": section_id}

    try:
        async with httpx.AsyncClient(timeout=settings.context_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException:
        raise AppError(
            "CONTEXT_SERVICE_ERROR",
            "El servicio de contenido tardó demasiado en responder.",
            502,
        )
    except httpx.HTTPError:
        raise AppError(
            "CONTEXT_SERVICE_ERROR",
            "No se pudo conectar con el servicio de contenido.",
            502,
        )

    if response.status_code == 404:
        code = _extract_error_code(response)
        if code == "BOOK_NOT_FOUND":
            raise AppError("BOOK_NOT_FOUND", f"El libro '{book_id}' no existe.", 404)
        if code == "SECTION_NOT_FOUND":
            raise AppError(
                "SECTION_NOT_FOUND",
                f"La sección '{section_id}' no existe en el libro '{book_id}'.",
                404,
            )
        raise AppError(
            "CONTEXT_SERVICE_ERROR",
            "El servicio de contenido devolvió un 404 inesperado.",
            502,
        )

    if response.status_code != 200:
        raise AppError(
            "CONTEXT_SERVICE_ERROR",
            f"El servicio de contenido respondió con HTTP {response.status_code}.",
            502,
        )

    try:
        return SectionContext.model_validate(response.json())
    except (ValueError, ValidationError):
        raise AppError(
            "CONTEXT_SERVICE_ERROR",
            "El servicio de contenido devolvió una respuesta inválida.",
            502,
        )


def _extract_error_code(response: httpx.Response) -> str | None:
    try:
        return response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None