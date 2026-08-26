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

router = APIRouter()


def _logic():
    """Import AI logic only when an AI endpoint is used."""
    from backend import ai_logic

    return ai_logic


# ── Models ────────────────────────────────────────────────────────────────────


class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str


class ProviderModelPayload(BaseModel):
    provider: str
    model: str


class BaseUrlChoicePayload(BaseModel):
    choice_key: str


class BaseUrlPayload(BaseModel):
    base_url: str


class LocalBaseUrlChoicePayload(BaseModel):
    choice_key: str
    custom_base_url: str = ""


class FetchModelsPayload(BaseModel):
    provider: str
    api_key: str = ""
    base_url_override: str = ""


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
    logic = _logic()
    logic.load_persisted_ai_settings()
    settings = logic._load_app_settings()
    providers = {}
    for provider in logic.AI_PROVIDER_PRIORITY:
        key_slot = provider
        env_var = logic.get_ai_provider_env_var(provider)
        if provider == "openai_compatible":
            choice = logic.get_openai_compatible_base_url_choice()
            key_slot = logic.get_openai_compatible_storage_key_name(choice)
            env_var = logic.get_openai_compatible_env_var(choice)
        key_configured = False
        if provider != "local":
            key_configured = logic.is_ai_api_key_configured(key_slot, env_var)
        providers[provider] = {
            "display_name": logic.get_ai_provider_display_name(provider),
            "env_var": env_var,
            "model": logic.get_ai_provider_model(provider),
            "default_models": logic.get_provider_default_models(provider),
            "key_configured": key_configured,
        }
    settings["providers"] = providers
    settings["provider_order"] = list(logic.AI_PROVIDER_PRIORITY)
    settings_provider = settings.get("ai_provider", "")
    settings["ai_provider"] = logic._normalize_provider_name(
        (settings_provider if isinstance(settings_provider, str) else "").strip()
        or os.getenv("AI_PROVIDER", "")
    )
    settings["openai_compatible_base_url_choice"] = (
        logic.get_openai_compatible_base_url_choice()
    )
    settings["openai_compatible_base_url_options"] = (
        logic.get_openai_compatible_base_url_options()
    )
    settings["local_ai_base_url"] = logic.get_local_ai_base_url()
    settings["local_ai_base_url_choice"] = logic.get_local_ai_base_url_choice()
    settings["local_ai_custom_base_url"] = logic.get_local_ai_custom_base_url()
    settings["local_ai_base_url_options"] = logic.get_local_ai_base_url_options()
    settings["secure_key_storage_available"] = logic.is_secure_key_storage_available()
    return settings


@router.post("/settings/provider")
def set_provider(provider: str):
    """Set the active AI provider."""
    logic = _logic()
    if provider not in logic.AI_PROVIDER_PRIORITY:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    logic.set_current_ai_provider(provider)
    return {"provider": provider}


@router.post("/settings/model")
def set_model(payload: ProviderModelPayload):
    """Set the model for a given provider."""
    _logic().set_ai_provider_model(payload.provider, payload.model)
    return {"provider": payload.provider, "model": payload.model}


@router.post("/settings/apikey")
def save_api_key(payload: ApiKeyPayload):
    """Store an API key securely for the given provider."""
    logic = _logic()
    provider = payload.provider
    if provider == "openai_compatible":
        provider = logic.get_openai_compatible_storage_key_name()
    logic.set_secure_ai_api_key(provider, payload.api_key)
    return {"provider": payload.provider, "saved": True}


@router.delete("/settings/apikey/{provider}")
def remove_api_key(provider: str):
    """Delete the stored API key for the given provider."""
    _logic().delete_secure_ai_api_key(provider)
    return {"provider": provider, "deleted": True}


@router.get("/settings/openai-compatible/base-url-options")
def openai_compatible_base_url_options():
    return _logic().get_openai_compatible_base_url_options()


@router.get("/settings/openai-compatible/base-url-choice")
def openai_compatible_base_url_choice():
    return {"choice": _logic().get_openai_compatible_base_url_choice()}


@router.post("/settings/openai-compatible/base-url-choice")
def set_openai_compatible_base_url(payload: BaseUrlChoicePayload):
    _logic().set_openai_compatible_base_url_choice(payload.choice_key)
    return {"choice": payload.choice_key}


@router.get("/settings/local/base-url")
def local_ai_base_url():
    return {"base_url": _logic().get_local_ai_base_url()}


@router.post("/settings/local/base-url")
def set_local_ai_base_url(payload: BaseUrlPayload):
    return {"base_url": _logic().set_local_ai_base_url(payload.base_url)}


@router.post("/settings/local/base-url-choice")
def set_local_ai_base_url_choice(payload: LocalBaseUrlChoicePayload):
    logic = _logic()
    choice = logic.set_local_ai_base_url_choice(
        payload.choice_key, custom_base_url=payload.custom_base_url
    )
    return {"choice": choice, "base_url": logic.get_local_ai_base_url()}


@router.get("/models/{provider}")
def get_models(provider: str, base_url_override: str = ""):
    """Fetch available models for a provider (live API call)."""
    logic = _logic()
    key_slot = provider
    if provider == "openai_compatible":
        key_slot = logic.get_openai_compatible_storage_key_name()
        override = (base_url_override or "").strip()
        for option in logic.get_openai_compatible_base_url_options():
            if override.rstrip("/") == str(option["url"]).rstrip("/"):
                key_slot = logic.get_openai_compatible_storage_key_name(option["key"])
                break
    api_key = "" if provider == "local" else logic.get_secure_ai_api_key(key_slot)
    try:
        models = logic.fetch_available_models(
            provider, api_key, base_url_override=base_url_override
        )
        message = ""
    except Exception:
        if provider == "local":
            return {
                "provider": provider,
                "models": [],
                "message": "Local model provider is not reachable.",
            }
        # Fall back to default list when the API is unreachable
        models = logic.get_provider_default_models(provider)
        message = ""
    return {"provider": provider, "models": models, "message": message}


@router.post("/models")
def fetch_models_with_key(payload: FetchModelsPayload):
    """Fetch available models using a supplied key without persisting it."""
    logic = _logic()
    try:
        models = logic.fetch_available_models(
            payload.provider,
            payload.api_key,
            base_url_override=payload.base_url_override,
        )
        message = ""
    except Exception:
        if payload.provider == "local":
            return {
                "provider": payload.provider,
                "models": [],
                "message": "Local model provider is not reachable.",
            }
        models = logic.get_provider_default_models(
            payload.provider, base_url_override=payload.base_url_override
        )
        message = ""
    return {"provider": payload.provider, "models": models, "message": message}


# ── Chat / automation endpoints ────────────────────────────────────────────────


@router.post("/chat")
def ai_chat(payload: AgentChatPayload):
    """Send a message to the AI agent and return a structured response."""
    logic = _logic()
    try:
        result = logic.request_ai_agent_response(
            payload.message,
            document_text=payload.document_text,
            selected_text=payload.selected_text,
            chat_history=payload.chat_history,
        )
    except logic.TranslationConfigError as exc:
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
    return {"histories": _logic().load_ai_chat_histories()}


@router.post("/chat/history")
def save_chat_history(histories: list[dict[str, Any]]):
    """Persist AI chat histories."""
    _logic().save_ai_chat_histories(histories)
    return {"saved": True}


@router.get("/automation/templates")
def automation_templates():
    """Return built-in AI automation task templates."""
    return {"templates": _logic().get_ai_automation_task_templates()}


@router.get("/automation/logs")
def automation_logs(limit: int = 100):
    """Return AI automation audit log entries."""
    return {"logs": _logic().load_ai_automation_logs(limit=limit)}


# ── Translation endpoint ───────────────────────────────────────────────────────


@router.post("/translate")
def translate(payload: TranslatePayload):
    logic = _logic()
    try:
        result = logic.translate_markdown_with_ai(
            payload.content, payload.source_language, payload.target_language
        )
    except logic.TranslationConfigError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "provider": getattr(exc, "provider_name", None),
                "env_var": getattr(exc, "env_var", None),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        result = (
            result.get("translated_markdown") or result.get("translated") or str(result)
        )

    return {"translated": result}
