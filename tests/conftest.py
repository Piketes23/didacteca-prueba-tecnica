import pytest
from fastapi.testclient import TestClient

from src.context_client import SectionContext
from src.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def section():
    return SectionContext(
        book_id="book_001",
        section_id="section_04",
        title="Ecuaciones cuadráticas",
        content=(
            "Una ecuación cuadrática tiene la forma ax² + bx + c = 0. "
            "El discriminante es Δ = b² − 4ac."
        ),
    )


@pytest.fixture
def fake_context(monkeypatch, section):
    """Reemplaza al Context Service por una sección fija."""

    async def _fetch(book_id, section_id):
        return section

    monkeypatch.setattr("src.main.fetch_context", _fetch)
    return section


class FakeLLM:
    def __init__(self):
        self.queue = []
        self.calls = 0

    def reply(self, *envelopes):
        self.queue.extend(envelopes)


@pytest.fixture
def fake_llm(monkeypatch):
    """Reemplaza a OpenAI: devuelve las respuestas encoladas, en orden."""
    fake = FakeLLM()

    async def _generate(system_prompt, user_prompt):
        fake.calls += 1
        return fake.queue.pop(0)

    monkeypatch.setattr("src.generator.generate_json", _generate)
    return fake