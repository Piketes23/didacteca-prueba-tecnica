from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------- Entrada ----------

class ExecuteRequest(BaseModel):
    action: str | None = None
    book_id: str | None = None
    section_id: str | None = None
    instructions: str | None = None


# ---------- Salidas exitosas (según el PDF) ----------

class ChatResponse(BaseModel):
    action: Literal["chat"] = "chat"
    answer: str = Field(min_length=1)
    assumptions: list[str] | None = None


class QuizQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str]
    correct_answer: str
    explanation: str = Field(min_length=1)

    @field_validator("options")
    @classmethod
    def exactly_four_options(cls, v: list[str]) -> list[str]:
        if len(v) != 4 or len(set(v)) != 4 or any(not o.strip() for o in v):
            raise ValueError("Cada pregunta necesita 4 opciones distintas y no vacías")
        return v

    @model_validator(mode="after")
    def answer_in_options(self) -> "QuizQuestion":
        if self.correct_answer not in self.options:
            raise ValueError("correct_answer debe ser una de las opciones")
        return self


class QuizResponse(BaseModel):
    action: Literal["quiz"] = "quiz"
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    questions: list[QuizQuestion] = Field(min_length=1)
    assumptions: list[str] | None = None


class ActivityResponse(BaseModel):
    action: Literal["activity"] = "activity"
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    estimated_time_minutes: int = Field(gt=0)
    expected_result: str = Field(min_length=1)
    assumptions: list[str] | None = None


# ---------- Salidas no exitosas ----------

class ErrorResponse(BaseModel):
    status: Literal["error", "needs_clarification", "partial"]
    code: str                      # ej. SECTION_NOT_FOUND, MISSING_FIELDS
    message: str                   # explicación legible para el usuario
    missing_fields: list[str] = []  # qué debe enviar el usuario
    details: dict = {}             # supuestos aplicados, parte no resuelta, etc.