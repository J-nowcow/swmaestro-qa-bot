"""Unit tests for portfolio.llm — mocks requests.post."""
from unittest.mock import MagicMock, patch

import pytest

from portfolio.llm import (
    LLMUnavailableError,
    MM_MODELS,
    TEXT_FALLBACK,
    call_multimodal,
)
from portfolio.parser import ImageData


def _ok_response(text: str = '{"ok": true}') -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": text}]}}
        ],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
    }
    return resp


def _rate_limited_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 429
    return resp


def _image() -> ImageData:
    return ImageData(filename="x.png", mime_type="image/png", base64="aGVsbG8=", original_index=0)


@patch("portfolio.llm.req.post")
def test_call_multimodal_first_model_succeeds(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    mock_post.return_value = _ok_response('{"x": 1}')

    text, model, tokens = call_multimodal(
        system_prompt="sys",
        user_text="hello",
        images=[_image()],
    )
    assert text == '{"x": 1}'
    assert model == MM_MODELS[0]
    assert tokens == {"input": 100, "output": 50}
    assert mock_post.call_count == 1


@patch("portfolio.llm.req.post")
def test_call_multimodal_falls_back_on_429(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    mock_post.side_effect = [
        _rate_limited_response(),
        _rate_limited_response(),
        _ok_response('{"ok": 1}'),
    ]

    text, model, _ = call_multimodal(
        system_prompt="sys",
        user_text="hello",
        images=[_image()],
    )
    assert text == '{"ok": 1}'
    assert model == MM_MODELS[2]
    assert mock_post.call_count == 3


@patch("portfolio.llm.req.post")
def test_call_multimodal_falls_back_to_text_only(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    responses = [_rate_limited_response()] * len(MM_MODELS) + [_ok_response('{"ok": 2}')]
    mock_post.side_effect = responses

    text, model, _ = call_multimodal(
        system_prompt="sys",
        user_text="hello",
        images=[_image()],
    )
    assert text == '{"ok": 2}'
    assert model == TEXT_FALLBACK[0]
    last_call = mock_post.call_args_list[-1]
    payload = last_call.kwargs["json"]
    parts = payload["contents"][0]["parts"]
    assert all("inline_data" not in p for p in parts)


@patch("portfolio.llm.req.post")
def test_call_multimodal_all_fail_raises(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    mock_post.return_value = _rate_limited_response()

    with pytest.raises(LLMUnavailableError):
        call_multimodal(system_prompt="s", user_text="u", images=[])


@patch("portfolio.llm.req.post")
def test_call_multimodal_uses_byok_key(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")
    mock_post.return_value = _ok_response()

    call_multimodal(system_prompt="s", user_text="u", images=[], api_key="byok-key")

    url = mock_post.call_args.args[0]
    assert "byok-key" in url
    assert "env-key" not in url


def test_call_multimodal_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        call_multimodal(system_prompt="s", user_text="u", images=[])


@patch("portfolio.llm.req.post")
def test_call_multimodal_prefers_portfolio_specific_env_key(mock_post, monkeypatch):
    """GOOGLE_API_KEY_PORTFOLIO should be preferred over GOOGLE_API_KEY."""
    monkeypatch.setenv("GOOGLE_API_KEY", "shared-key")
    monkeypatch.setenv("GOOGLE_API_KEY_PORTFOLIO", "portfolio-key")
    mock_post.return_value = _ok_response()

    call_multimodal(system_prompt="s", user_text="u", images=[])

    url = mock_post.call_args.args[0]
    assert "portfolio-key" in url
    assert "shared-key" not in url
