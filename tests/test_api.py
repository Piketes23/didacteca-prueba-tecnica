BODY = {
    "action": "quiz",
    "book_id": "book_001",
    "section_id": "section_04",
    "instructions": "Genera un quiz de 1 pregunta de dificultad intermedia.",
}


def post(client, **changes):
    body = {**BODY, **changes}
    body = {k: v for k, v in body.items() if v is not None}
    return client.post("/execute", json=body)


def quiz_envelope(n_options=4, status="ok", reason=""):
    options = ["ax² + bx + c = 0", "ax + b = 0", "ax³ + c = 0", "a + bx = 0"][:n_options]
    return {
        "status": status,
        "reason": reason,
        "assumptions": [],
        "resource": {
            "title": "Quiz",
            "instructions": "Elige la opción correcta.",
            "questions": [
                {
                    "question": "¿Cuál es la forma general?",
                    "options": options,
                    "correct_answer": options[0],
                    "explanation": "Lo dice el texto.",
                }
            ],
        },
    }


# ---------- Validación de la solicitud (antes de llamar a servicios externos) ----------

def test_missing_section_id_asks_for_clarification(client):
    r = post(client, section_id=None)
    data = r.json()
    assert r.status_code == 422
    assert data["status"] == "needs_clarification"
    assert data["code"] == "MISSING_FIELDS"
    assert data["missing_fields"] == ["section_id"]


def test_unsupported_action_is_rejected(client):
    r = post(client, action="resumen")
    assert r.status_code == 400
    assert r.json()["code"] == "UNSUPPORTED_ACTION"


def test_contradictory_quiz_counts_ask_for_clarification(client):
    r = post(client, instructions="Genera un quiz de 3 preguntas y también de 10 preguntas.")
    data = r.json()
    assert r.status_code == 422
    assert data["status"] == "needs_clarification"
    assert data["code"] == "AMBIGUOUS_INSTRUCTIONS"


# ---------- Casos exitosos ----------

def test_quiz_success_matches_schema(client, fake_context, fake_llm):
    fake_llm.reply(quiz_envelope())
    r = post(client)
    data = r.json()
    assert r.status_code == 200
    assert data["action"] == "quiz"
    question = data["questions"][0]
    assert len(question["options"]) == 4
    assert question["correct_answer"] in question["options"]
    assert "assumptions" not in data  # el usuario dio cantidad y dificultad


def test_quiz_declares_defaults_it_applied(client, fake_context, fake_llm):
    fake_llm.reply(quiz_envelope())
    r = post(client, instructions="Genera un quiz")
    assumptions = r.json()["assumptions"]
    assert any("Cantidad" in a for a in assumptions)
    assert any("Dificultad" in a for a in assumptions)


# ---------- Casos problemáticos ----------

def test_empty_section_never_reaches_the_model(client, fake_context, fake_llm):
    fake_context.content = ""
    r = post(client)
    assert r.status_code == 422
    assert r.json()["code"] == "CONTENT_INSUFFICIENT"
    assert fake_llm.calls == 0


def test_model_reports_insufficient_content(client, fake_context, fake_llm):
    fake_llm.reply(
        {"status": "insufficient_content", "reason": "El libro no habla de eso."}
    )
    r = post(client, action="chat", instructions="¿Quién descubrió América?")
    data = r.json()
    assert r.status_code == 422
    assert data["code"] == "CONTENT_INSUFFICIENT"
    assert data["message"] == "El libro no habla de eso."


def test_partial_result_is_distinguishable_from_success(client, fake_context, fake_llm):
    fake_llm.reply(quiz_envelope(status="partial", reason="Solo alcanza para 1 pregunta."))
    r = post(client)
    data = r.json()
    assert data["status"] == "partial"
    assert data["code"] == "PARTIAL_RESULT"
    assert data["details"]["resource"]["action"] == "quiz"


# ---------- Validación de la salida del modelo ----------

def test_invalid_output_is_retried_and_can_recover(client, fake_context, fake_llm):
    fake_llm.reply(quiz_envelope(n_options=3), quiz_envelope())
    r = post(client)
    assert r.status_code == 200
    assert r.json()["action"] == "quiz"
    assert fake_llm.calls == 2


def test_invalid_output_twice_is_an_error_not_a_success(client, fake_context, fake_llm):
    fake_llm.reply(quiz_envelope(n_options=3), quiz_envelope(n_options=3))
    r = post(client)
    assert r.status_code == 502
    assert r.json()["code"] == "INVALID_MODEL_OUTPUT"
    assert fake_llm.calls == 2


def test_output_of_another_action_is_not_accepted(client, fake_context, fake_llm):
    """Si el modelo es manipulado y responde como 'chat' a un quiz, no pasa."""
    hijacked = {"status": "ok", "resource": {"answer": "Colón, en 1492."}}
    fake_llm.reply(hijacked, hijacked)
    r = post(client)
    assert r.status_code == 502
    assert r.json()["code"] == "INVALID_MODEL_OUTPUT"


# ---------- Errores inesperados ----------

def test_unexpected_exception_returns_generic_error(client, monkeypatch):
    async def boom(book_id, section_id):
        raise RuntimeError("fallo interno")

    monkeypatch.setattr("src.main.fetch_context", boom)
    r = post(client)
    assert r.status_code == 500
    data = r.json()
    assert data["code"] == "INTERNAL_ERROR"
    assert "fallo interno" not in data["message"]  # no se filtran detalles internos