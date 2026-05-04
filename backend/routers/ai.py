"""
backend/routers/ai.py
=====================
AI provider configuration and chat / automation endpoints.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markdown_reader.logic import (
    AI_PROVIDER_PRIORITY,
    TranslationConfigError,
    delete_secure_ai_api_key,
    fetch_available_models,
    get_ai_automation_task_templates,
    get_ai_provider_display_name,
    get_ai_provider_env_var,
    get_ai_provider_model,
    get_openai_compatible_base_url_choice,
    get_openai_compatible_base_url_options,
    get_openai_compatible_storage_key_name,
    get_provider_default_models,
    get_secure_ai_api_key,
    load_ai_automation_logs,
    load_ai_chat_histories,
    load_persisted_ai_settings,
    request_ai_agent_response,
    save_ai_chat_histories,
    set_ai_provider_model,
    set_current_ai_provider,
    set_openai_compatible_base_url_choice,
    set_secure_ai_api_key,
    translate_markdown_with_ai,
)

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────


class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str


class ProviderModelPayload(BaseModel):
    provider: str
    model: str


class BaseUrlChoicePayload(BaseModel):
    choice_key: str


class AgentChatPayload(BaseModel):
    message: str
    document_text: str = ""
    selected_text: str = ""
    chat_history: list[dict[str, Any]] = []


class TranslatePayload(BaseModel):
    content: str
    source_language: str
    target_language: str


# ── Settings endpoints ─────────────────────────────────────────────────────────


@router.get("/settings")
def get_ai_settings():
    """Return all persisted AI provider settings."""
    settings = load_persisted_ai_settings()
    # Augment with display names and env var names
    for provider in AI_PROVIDER_PRIORITY:
        settings.setdefault("providers", {})
        settings["providers"][provider] = {
            "display_name": get_ai_provider_display_name(provider),
            "env_var": get_ai_provider_env_var(provider),
            "model": get_ai_provider_model(provider),
            "default_models": get_provider_default_models(provider),
        }
    return settings


@router.post("/settings/provider")
def set_provider(provider: str):
    """Set the active AI provider."""
    if provider not in AI_PROVIDER_PRIORITY:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    set_current_ai_provider(provider)
    return {"provider": provider}


@router.post("/settings/model")
def set_model(payload: ProviderModelPayload):
    """Set the model for a given provider."""
    set_ai_provider_model(payload.provider, payload.model)
    return {"provider": payload.provider, "model": payload.model}


@router.post("/settings/apikey")
def save_api_key(payload: ApiKeyPayload):
    """Store an API key securely for the given provider."""
    set_secure_ai_api_key(payload.provider, payload.api_key)
    return {"provider": payload.provider, "saved": True}


@router.delete("/settings/apikey/{provider}")
def remove_api_key(provider: str):
    """Delete the stored API key for the given provider."""
    delete_secure_ai_api_key(provider)
    return {"provider": provider, "deleted": True}


@router.get("/settings/openai-compatible/base-url-options")
def openai_compatible_base_url_options():
    return get_openai_compatible_base_url_options()


@router.get("/settings/openai-compatible/base-url-choice")
def openai_compatible_base_url_choice():
    return {"choice": get_openai_compatible_base_url_choice()}


@router.post("/settings/openai-compatible/base-url-choice")
def set_openai_compatible_base_url(payload: BaseUrlChoicePayload):
    set_openai_compatible_base_url_choice(payload.choice_key)
    return {"choice": payload.choice_key}


@router.get("/models/{provider}")
def get_models(provider: str, base_url_override: str = ""):
    """Fetch available models for a provider (live API call)."""
    api_key = get_secure_ai_api_key(
        get_openai_compatible_storage_key_name()
        if provider == "openai_compatible"
        else provider
    )
    try:
        models = fetch_available_models(
            provider, api_key, base_url_override=base_url_override
        )
    except Exception:
        # Fall back to default list when the API is unreachable
        models = get_provider_default_models(provider)
    return {"provider": provider, "models": models}


# ── Chat / automation endpoints ────────────────────────────────────────────────


@router.post("/chat")
def ai_chat(payload: AgentChatPayload):
    """Send a message to the AI agent and return a structured response."""
    try:
        result = request_ai_agent_response(
            payload.message,
            document_text=payload.document_text,
            selected_text=payload.selected_text,
            chat_history=payload.chat_history,
        )
    except TranslationConfigError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "provider": getattr(exc, "provider_name", None),
                "env_var": getattr(exc, "env_var", None),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.get("/chat/history")
def get_chat_history():
    """Load all persisted AI chat histories."""
    return {"histories": load_ai_chat_histories()}


@router.post("/chat/history")
def save_chat_history(histories: list[dict[str, Any]]):
    """Persist AI chat histories."""
    save_ai_chat_histories(histories)
    return {"saved": True}


@router.get("/automation/templates")
def automation_templates():
    """Return built-in AI automation task templates."""
    return {"templates": get_ai_automation_task_templates()}


@router.get("/automation/logs")
def automation_logs(limit: int = 100):
    """Return AI automation audit log entries."""
    return {"logs": load_ai_automation_logs(limit=limit)}


# ── Translation endpoint ───────────────────────────────────────────────────────


@router.post("/translate")
def translate(payload: TranslatePayload):
    try:
        result = translate_markdown_with_ai(
            payload.content, payload.source_language, payload.target_language
        )
    except TranslationConfigError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "provider": getattr(exc, "provider_name", None)},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        result = result.get("translated_markdown") or result.get("translated") or str(result)

    return {"translated": result}
