import json

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from src.config import settings
from src.errors import AppError

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if not settings.openai_api_key:
        raise AppError(
            "LLM_ERROR",
            "El servicio de IA no está configurado (falta OPENAI_API_KEY).",
            500,
        )
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
        )
    return _client


async def generate_json(system_prompt: str, user_prompt: str) -> dict:
    """Llama al modelo y devuelve un dict con el JSON generado.

    Nota: el modo JSON de OpenAI exige que la palabra "JSON" aparezca
    en los mensajes; los prompts de cada servicio deben incluirla.
    """
    client = _get_client()

    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except APITimeoutError:
        raise AppError("LLM_ERROR", "El servicio de IA tardó demasiado en responder.", 502)
    except APIConnectionError:
        raise AppError("LLM_ERROR", "No se pudo conectar con el servicio de IA.", 502)
    except APIStatusError as exc:
        raise AppError(
            "LLM_ERROR",
            f"El servicio de IA respondió con un error (HTTP {exc.status_code}).",
            502,
        )

    text = completion.choices[0].message.content or ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise AppError(
            "INVALID_MODEL_OUTPUT",
            "El modelo devolvió una respuesta que no es JSON válido.",
            502,
        )

    if not isinstance(data, dict):
        raise AppError(
            "INVALID_MODEL_OUTPUT",
            "El modelo devolvió JSON con una estructura inesperada.",
            502,
        )
    return data