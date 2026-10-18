import httpx
import pytest
import respx

from src.config import settings
from src.context_client import fetch_context
from src.errors import AppError

URL = f"{settings.provided_service_base_url.rstrip('/')}/context"
OK_BODY = {
    "book_id": "book_001",
    "section_id": "section_04",
    "title": "Ecuaciones cuadráticas",
    "content": "Texto de la sección.",
}


@respx.mock
async def test_returns_section_content():
    respx.post(URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    ctx = await fetch_context("book_001", "section_04")
    assert ctx.title == "Ecuaciones cuadráticas"
    assert ctx.content == "Texto de la sección."


@respx.mock
async def test_empty_content_is_not_a_transport_error():
    respx.post(URL).mock(return_value=httpx.Response(200, json={**OK_BODY, "content": ""}))
    ctx = await fetch_context("book_001", "section_04")
    assert ctx.content == ""


@respx.mock
async def test_book_not_found():
    body = {"error": {"code": "BOOK_NOT_FOUND", "message": "x"}}
    respx.post(URL).mock(return_value=httpx.Response(404, json=body))
    with pytest.raises(AppError) as exc:
        await fetch_context("book_inexistente", "section_01")
    assert exc.value.code == "BOOK_NOT_FOUND"
    assert exc.value.http_status == 404


@respx.mock
async def test_section_not_found():
    body = {"error": {"code": "SECTION_NOT_FOUND", "message": "x"}}
    respx.post(URL).mock(return_value=httpx.Response(404, json=body))
    with pytest.raises(AppError) as exc:
        await fetch_context("book_001", "section_inexistente")
    assert exc.value.code == "SECTION_NOT_FOUND"


@respx.mock
async def test_timeout_becomes_context_service_error():
    respx.post(URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(AppError) as exc:
        await fetch_context("book_001", "section_04")
    assert exc.value.code == "CONTEXT_SERVICE_ERROR"
    assert exc.value.http_status == 502


@respx.mock
async def test_invalid_response_body_is_rejected():
    respx.post(URL).mock(return_value=httpx.Response(200, json={"algo": "raro"}))
    with pytest.raises(AppError) as exc:
        await fetch_context("book_001", "section_04")
    assert exc.value.code == "CONTEXT_SERVICE_ERROR"


@respx.mock
async def test_server_error_becomes_context_service_error():
    respx.post(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(AppError) as exc:
        await fetch_context("book_001", "section_04")
    assert exc.value.code == "CONTEXT_SERVICE_ERROR"