import random
import re

from pydantic import ValidationError

from src.context_client import SectionContext
from src.errors import AppError
from src.llm_client import generate_json
from src.prompts import build_prompts
from src.schemas import ActivityResponse, ChatResponse, QuizResponse

RESPONSE_MODELS = {
    "chat": ChatResponse,
    "quiz": QuizResponse,
    "activity": ActivityResponse,
}
MAX_ATTEMPTS = 2

# Temas sobre los que el sistema puede aplicar un valor por defecto.
# "user": detecta si el usuario ya dio el dato en sus instrucciones.
# "model": detecta supuestos del modelo sobre ese mismo tema.
ASSUMPTION_TOPICS = {
    "cantidad": {
        "actions": ("quiz",),
        "user": r"\d",
        "model": r"pregunta|cantidad|n[uú]mero",
    },
    "dificultad": {
        "actions": ("quiz",),
        "user": r"f[aá]cil|intermedi|dif[ií]cil|b[aá]sic|avanzad",
        "model": r"dificultad|nivel",
    },
    "duracion": {
        "actions": ("activity",),
        "user": r"\d+\s*(min|h)|minuto|\bhoras?\b",
        "model": r"duraci|minuto|tiempo|\bhoras?\b",
    },
}


def _system_assumption(topic: str, result) -> str:
    if topic == "cantidad":
        return f"Cantidad de preguntas ({len(result.questions)}) elegida por el sistema."
    if topic == "dificultad":
        return "Dificultad intermedia aplicada por defecto."
    return f"Duración estimada de {result.estimated_time_minutes} minutos elegida por el sistema."


def reconcile_assumptions(action: str, instructions: str, result) -> list[str] | None:
    """El sistema, no el modelo, es la fuente de verdad sobre los valores por defecto."""
    assumptions = list(result.assumptions or [])
    for topic, rule in ASSUMPTION_TOPICS.items():
        if action not in rule["actions"]:
            continue
        assumptions = [
            a for a in assumptions if not re.search(rule["model"], a, re.IGNORECASE)
        ]
        if not re.search(rule["user"], instructions, re.IGNORECASE):
            assumptions.append(_system_assumption(topic, result))
    return assumptions or None


async def run_action(action: str, context: SectionContext, instructions: str):
    if not context.content.strip():
        raise AppError(
            "CONTENT_INSUFFICIENT",
            "La sección existe pero no tiene contenido para trabajar.",
            422,
        )

    model_cls = RESPONSE_MODELS[action]
    system_prompt, user_prompt = build_prompts(
        action, context.title, context.content, instructions
    )
    last_error = ""

    for _ in range(MAX_ATTEMPTS):
        prompt = user_prompt
        if last_error:
            prompt += (
                f"\n\nTu respuesta anterior no cumplió el formato ({last_error}). "
                "Corrígela y responde de nuevo solo con el JSON."
            )

        envelope = await generate_json(system_prompt, prompt)
        status = envelope.get("status")
        reason = str(envelope.get("reason") or "").strip()
        raw_assumptions = envelope.get("assumptions")
        assumptions = (
            [str(a) for a in raw_assumptions] if isinstance(raw_assumptions, list) else []
        )

        if status == "insufficient_content":
            raise AppError(
                "CONTENT_INSUFFICIENT",
                reason or "El contenido de la sección no permite cumplir la solicitud.",
                422,
            )
        if status == "conflicting_instructions":
            raise AppError(
                "AMBIGUOUS_INSTRUCTIONS",
                reason or "Las instrucciones son contradictorias. Envía una versión aclarada.",
                422,
                status="needs_clarification",
            )
        if status not in ("ok", "partial"):
            last_error = "el campo 'status' tiene un valor no permitido"
            continue

        resource = envelope.get("resource")
        if not isinstance(resource, dict):
            last_error = "falta el objeto 'resource'"
            continue

        try:
            result = model_cls.model_validate(
                {**resource, "action": action, "assumptions": assumptions or None}
            )
        except ValidationError as exc:
            last_error = str(exc).replace("\n", " ")[:300]
            continue

        result.assumptions = reconcile_assumptions(action, instructions, result)

        if action == "quiz":
            for question in result.questions:
                random.shuffle(question.options)

        if status == "partial":
            raise AppError(
                "PARTIAL_RESULT",
                reason or "Solo se pudo resolver una parte de la solicitud.",
                200,
                status="partial",
                details={"resource": result.model_dump(exclude_none=True)},
            )
        return result

    raise AppError(
        "INVALID_MODEL_OUTPUT",
        "El modelo no produjo una respuesta con el formato esperado.",
        502,
    )