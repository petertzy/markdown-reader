from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

import requests

try:
    import keyring
    from keyring.errors import KeyringError
except Exception:
    keyring = None

    class KeyringError(Exception):
        pass


AI_CREDENTIAL_SERVICE = "MarkdownReader.AI"
LOCAL_AI_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
LOCAL_AI_BASE_URL_OPTIONS = {
    "lm_studio": "http://127.0.0.1:1234/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "custom": "",
}
LOCAL_AI_BASE_URL_LABELS = {
    "lm_studio": "LM Studio",
    "ollama": "Ollama",
    "custom": "Custom",
}
OPENAI_COMPATIBLE_BASE_URL_OPTIONS = {
    "navidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
}
OPENAI_COMPATIBLE_BASE_URL_LABELS = {"navidia": "Navidia", "groq": "Groq"}
OPENAI_COMPATIBLE_DEFAULT_MODELS_BY_BASE_OPTION = {
    "navidia": [
        "mistralai/mistral-large-3-675b-instruct-2512",
        "mistralai/mistral-medium-3-instruct",
        "mistralai/mistral-small-3.1-24b-instruct-2503",
    ],
    "groq": [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
    ],
}
AI_PROVIDER_PRIORITY = (
    "local",
    "openai_compatible",
    "openrouter",
    "openai",
    "anthropic",
)
AI_PROVIDER_BASE_URLS = {
    "local": LOCAL_AI_DEFAULT_BASE_URL,
    "openai_compatible": OPENAI_COMPATIBLE_BASE_URL_OPTIONS["navidia"],
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}
AI_PROVIDER_DEFAULT_MODELS = {
    "local": [],
    "openrouter": ["meta-llama/llama-3.3-70b-instruct:free", "openai/gpt-4o-mini"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
}
AI_PROVIDER_MODEL_ENV = {
    "local": "LOCAL_AI_MODEL",
    "openai_compatible": "OPENAI_COMPATIBLE_MODEL",
    "openrouter": "OPENROUTER_MODEL",
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
}
AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES = 300
AI_AUTOMATION_TASK_TEMPLATES = [
    {
        "id": "format_selection",
        "title": "Format Selected Section",
        "prompt": "Apply Markdown formatting rules to the selected section.",
        "requires_selection": True,
    },
    {
        "id": "generate_toc",
        "title": "Generate Table of Contents",
        "prompt": "Generate a Markdown table of contents from headings and insert it.",
        "requires_selection": False,
    },
    {
        "id": "generate_summary",
        "title": "Generate Summary",
        "prompt": "Generate a concise document summary in Markdown bullet points.",
        "requires_selection": False,
    },
    {
        "id": "fix_code_blocks",
        "title": "Format and Fix Code Blocks",
        "prompt": "Format Markdown code fences and fix common fence syntax issues.",
        "requires_selection": False,
    },
]


class TranslationConfigError(RuntimeError):
    def __init__(
        self, message: str, provider_name: str | None = None, env_var: str | None = None
    ):
        super().__init__(message)
        self.provider_name = provider_name
        self.env_var = env_var


def _get_settings_file_path() -> Path:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / "MarkdownReader"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        base_dir = (
            Path(appdata) / "MarkdownReader"
            if appdata
            else Path.home() / "AppData" / "Roaming" / "MarkdownReader"
        )
    else:
        base_dir = Path.home() / ".config" / "markdown-reader"
    return base_dir / "settings.json"


APP_SETTINGS_FILE_PATH = _get_settings_file_path()
AI_CHAT_HISTORY_FILE_PATH = APP_SETTINGS_FILE_PATH.parent / "chat_history.json"
AI_AUTOMATION_LOG_FILE_PATH = APP_SETTINGS_FILE_PATH.parent / "ai_automation_log.json"


def _normalize_provider_name(provider: str) -> str:
    provider = (provider or "").strip().lower()
    return provider if provider in AI_PROVIDER_PRIORITY else "openai_compatible"


def _load_app_settings() -> dict[str, Any]:
    if not APP_SETTINGS_FILE_PATH.exists():
        return {}
    try:
        with open(APP_SETTINGS_FILE_PATH, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_app_settings(settings: dict[str, Any]) -> None:
    APP_SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_SETTINGS_FILE_PATH, "w", encoding="utf-8") as file_obj:
        json.dump(settings, file_obj, indent=2, ensure_ascii=False)


def load_persisted_ai_settings() -> None:
    settings = _load_app_settings()
    for key, value in settings.items():
        if isinstance(value, str) and key.isupper() and not os.getenv(key):
            os.environ[key] = value


def get_ai_provider_env_var(provider: str) -> str:
    provider = _normalize_provider_name(provider)
    return {
        "local": "LOCAL_AI_API_KEY",
        "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }[provider]


def _get_key_slot_env_var(provider_or_slot: str) -> str:
    provider_or_slot = (provider_or_slot or "").strip()
    for choice in OPENAI_COMPATIBLE_BASE_URL_OPTIONS:
        if provider_or_slot == get_openai_compatible_storage_key_name(choice):
            return get_openai_compatible_env_var(choice)
    return get_ai_provider_env_var(provider_or_slot)


def get_ai_provider_display_name(provider: str) -> str:
    return {
        "local": "Local Model",
        "openai_compatible": "OpenAI Compatible",
        "openrouter": "OpenRouter",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
    }.get(provider, provider)


def _build_provider_order(preferred_provider: str = "") -> list[str]:
    preferred = _normalize_provider_name(preferred_provider)
    order = [preferred]
    order.extend(provider for provider in AI_PROVIDER_PRIORITY if provider != preferred)
    return order


def get_openai_compatible_base_url_options() -> list[dict[str, str]]:
    return [
        {"key": key, "label": OPENAI_COMPATIBLE_BASE_URL_LABELS[key], "url": url}
        for key, url in OPENAI_COMPATIBLE_BASE_URL_OPTIONS.items()
    ]


def get_local_ai_base_url_options() -> list[dict[str, str]]:
    return [
        {"key": key, "label": LOCAL_AI_BASE_URL_LABELS[key], "url": url}
        for key, url in LOCAL_AI_BASE_URL_OPTIONS.items()
    ]


def get_openai_compatible_base_url_choice() -> str:
    choice = (
        os.getenv("OPENAI_COMPATIBLE_BASE_URL_CHOICE")
        or _load_app_settings().get("openai_compatible_base_url_choice")
        or "navidia"
    ).strip()
    return choice if choice in OPENAI_COMPATIBLE_BASE_URL_OPTIONS else "navidia"


def set_openai_compatible_base_url_choice(choice_key: str) -> str:
    choice = (
        choice_key if choice_key in OPENAI_COMPATIBLE_BASE_URL_OPTIONS else "navidia"
    )
    os.environ["OPENAI_COMPATIBLE_BASE_URL_CHOICE"] = choice
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = OPENAI_COMPATIBLE_BASE_URL_OPTIONS[
        choice
    ]
    settings = _load_app_settings()
    settings["openai_compatible_base_url_choice"] = choice
    _save_app_settings(settings)
    return choice


def get_openai_compatible_base_url() -> str:
    override = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return OPENAI_COMPATIBLE_BASE_URL_OPTIONS[get_openai_compatible_base_url_choice()]


def get_local_ai_base_url() -> str:
    settings = _load_app_settings()
    choice = str(settings.get("local_ai_base_url_choice", "")).strip()
    if choice in LOCAL_AI_BASE_URL_OPTIONS and choice != "custom":
        return LOCAL_AI_BASE_URL_OPTIONS[choice].rstrip("/")
    custom_url = str(settings.get("local_ai_custom_base_url", "")).strip()
    if choice == "custom" and custom_url:
        return custom_url.rstrip("/")
    env_url = os.getenv("LOCAL_AI_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    configured_url = (
        custom_url
        or str(settings.get("local_ai_base_url", "")).strip()
        or LOCAL_AI_DEFAULT_BASE_URL
    )
    return configured_url.rstrip("/")


def set_local_ai_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/") or LOCAL_AI_DEFAULT_BASE_URL
    os.environ["LOCAL_AI_BASE_URL"] = normalized
    settings = _load_app_settings()
    settings["local_ai_base_url_choice"] = "custom"
    settings["local_ai_custom_base_url"] = normalized
    settings["local_ai_base_url"] = normalized
    _save_app_settings(settings)
    return normalized


def get_local_ai_base_url_choice() -> str:
    choice = str(_load_app_settings().get("local_ai_base_url_choice", "")).strip()
    if choice in LOCAL_AI_BASE_URL_OPTIONS:
        return choice
    current_url = get_local_ai_base_url().rstrip("/")
    for key, option_url in LOCAL_AI_BASE_URL_OPTIONS.items():
        if option_url and current_url == option_url.rstrip("/"):
            return key
    return "custom" if current_url != LOCAL_AI_DEFAULT_BASE_URL else "lm_studio"


def get_local_ai_custom_base_url() -> str:
    custom_url = str(_load_app_settings().get("local_ai_custom_base_url", "")).strip()
    return custom_url.rstrip("/")


def set_local_ai_base_url_choice(choice_key: str, custom_base_url: str = "") -> str:
    choice = choice_key if choice_key in LOCAL_AI_BASE_URL_OPTIONS else "lm_studio"
    settings = _load_app_settings()
    settings["local_ai_base_url_choice"] = choice
    if custom_base_url.strip():
        settings["local_ai_custom_base_url"] = custom_base_url.strip().rstrip("/")
    resolved_url = (
        settings.get("local_ai_custom_base_url", "")
        if choice == "custom"
        else LOCAL_AI_BASE_URL_OPTIONS[choice]
    )
    resolved_url = str(resolved_url or LOCAL_AI_DEFAULT_BASE_URL).strip().rstrip("/")
    settings["local_ai_base_url"] = resolved_url
    os.environ["LOCAL_AI_BASE_URL"] = resolved_url
    _save_app_settings(settings)
    return choice


def get_openai_compatible_storage_key_name(choice_key: str | None = None) -> str:
    choice = choice_key or get_openai_compatible_base_url_choice()
    return (
        f"openai_compatible_{choice}"
        if choice in OPENAI_COMPATIBLE_BASE_URL_OPTIONS
        else "openai_compatible"
    )


def get_openai_compatible_env_var(choice_key: str | None = None) -> str:
    choice = choice_key or get_openai_compatible_base_url_choice()
    return (
        f"OPENAI_COMPATIBLE_{choice.upper()}_API_KEY"
        if choice in OPENAI_COMPATIBLE_BASE_URL_OPTIONS
        else "OPENAI_COMPATIBLE_API_KEY"
    )


def get_ai_provider_model(provider: str) -> str:
    provider = _normalize_provider_name(provider)
    env_var = AI_PROVIDER_MODEL_ENV[provider]
    settings_model = ""
    ai_models = _load_app_settings().get("ai_models", {})
    if isinstance(ai_models, dict):
        settings_model = str(ai_models.get(provider, "")).strip()
    return (
        os.getenv(env_var, "").strip()
        or settings_model
        or next(iter(get_provider_default_models(provider)), "")
    )


def set_ai_provider_model(provider: str, model: str) -> None:
    provider = _normalize_provider_name(provider)
    model = model.strip()
    os.environ[AI_PROVIDER_MODEL_ENV[provider]] = model
    settings = _load_app_settings()
    settings.setdefault("ai_models", {})
    if isinstance(settings["ai_models"], dict):
        settings["ai_models"][provider] = model
    _save_app_settings(settings)


def set_current_ai_provider(provider: str) -> None:
    provider = _normalize_provider_name(provider)
    os.environ["AI_PROVIDER"] = provider
    settings = _load_app_settings()
    settings["ai_provider"] = provider
    _save_app_settings(settings)


def get_provider_default_models(
    provider: str, base_url_override: str = ""
) -> list[str]:
    provider = _normalize_provider_name(provider)
    if provider == "openai_compatible":
        url = (base_url_override or get_openai_compatible_base_url()).rstrip("/")
        for key, option_url in OPENAI_COMPATIBLE_BASE_URL_OPTIONS.items():
            if url == option_url.rstrip("/"):
                return list(OPENAI_COMPATIBLE_DEFAULT_MODELS_BY_BASE_OPTION[key])
        return list(OPENAI_COMPATIBLE_DEFAULT_MODELS_BY_BASE_OPTION["navidia"])
    return list(AI_PROVIDER_DEFAULT_MODELS[provider])


def is_secure_key_storage_available() -> bool:
    return keyring is not None


def get_secure_ai_api_key(provider: str) -> str:
    if keyring is None:
        return os.getenv(_get_key_slot_env_var(provider), "")
    try:
        return keyring.get_password(AI_CREDENTIAL_SERVICE, provider) or ""
    except KeyringError:
        return ""


def is_ai_api_key_configured(
    provider: str, env_var: str = "", timeout_seconds: float = 1.0
) -> bool:
    if env_var and os.getenv(env_var, "").strip():
        return True
    if keyring is None:
        return bool(os.getenv(_get_key_slot_env_var(provider), "").strip())

    result = {"configured": False}

    def check_keyring() -> None:
        try:
            result["configured"] = bool(
                keyring.get_password(AI_CREDENTIAL_SERVICE, provider)
            )
        except KeyringError:
            result["configured"] = False

    thread = threading.Thread(target=check_keyring, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    return result["configured"] if not thread.is_alive() else False


def set_secure_ai_api_key(provider: str, api_key: str) -> None:
    if keyring is None:
        os.environ[_get_key_slot_env_var(provider)] = api_key
        return
    keyring.set_password(AI_CREDENTIAL_SERVICE, provider, api_key)


def delete_secure_ai_api_key(provider: str) -> None:
    if keyring is None:
        os.environ.pop(_get_key_slot_env_var(provider), None)
        return
    try:
        keyring.delete_password(AI_CREDENTIAL_SERVICE, provider)
    except KeyringError:
        pass


def fetch_available_models(
    provider: str, api_key: str, base_url_override: str = ""
) -> list[str]:
    provider = _normalize_provider_name(provider)
    if provider == "local":
        base_url = (base_url_override or get_local_ai_base_url()).rstrip("/")
    elif provider == "openai_compatible":
        base_url = (base_url_override or get_openai_compatible_base_url()).rstrip("/")
    else:
        base_url = AI_PROVIDER_BASE_URLS[provider].rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(f"{base_url}/models", headers=headers, timeout=20)
    try:
        response.raise_for_status()
    except requests.RequestException:
        if provider == "local" and base_url.endswith(":11434/v1"):
            tags_url = base_url.removesuffix("/v1") + "/api/tags"
            tags_response = requests.get(tags_url, timeout=20)
            tags_response.raise_for_status()
            tags_data = tags_response.json()
            tags_models = tags_data.get("models", [])
            if isinstance(tags_models, list):
                return [
                    item.get("name", "")
                    for item in tags_models
                    if isinstance(item, dict) and item.get("name")
                ]
        raise
    data = response.json()
    models = data.get("data", data)
    if isinstance(models, list):
        ids = [
            item.get("id") if isinstance(item, dict) else str(item) for item in models
        ]
        return [model for model in ids if model]
    return get_provider_default_models(provider, base_url_override=base_url_override)


def _get_current_ai_provider() -> str:
    load_persisted_ai_settings()
    settings_provider = _load_app_settings().get("ai_provider", "")
    persisted_provider = settings_provider if isinstance(settings_provider, str) else ""
    return _normalize_provider_name(
        persisted_provider.strip() or os.getenv("AI_PROVIDER", "")
    )


def _get_ai_api_key_for_provider(provider: str) -> tuple[str, str, str]:
    provider = _normalize_provider_name(provider)
    key_slot = provider
    env_var = get_ai_provider_env_var(provider)
    if provider == "openai_compatible":
        choice = get_openai_compatible_base_url_choice()
        key_slot = get_openai_compatible_storage_key_name(choice)
        env_var = get_openai_compatible_env_var(choice)

    api_key = os.getenv(env_var, "").strip() or get_secure_ai_api_key(key_slot).strip()
    if provider == "openai_compatible" and not api_key:
        fallback_env_var = get_ai_provider_env_var(provider)
        api_key = (
            os.getenv(fallback_env_var, "").strip()
            or get_secure_ai_api_key(provider).strip()
        )
        env_var = fallback_env_var
    return api_key, key_slot, env_var


def _get_ai_base_url(provider: str) -> str:
    provider = _normalize_provider_name(provider)
    if provider == "local":
        return get_local_ai_base_url().rstrip("/")
    if provider == "openai_compatible":
        return get_openai_compatible_base_url().rstrip("/")
    return AI_PROVIDER_BASE_URLS[provider].rstrip("/")


def _extract_openai_compatible_text(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
                and item.get("type") in {"text", "output_text"}
            )
    text = first_choice.get("text")
    return text if isinstance(text, str) else ""


def _extract_anthropic_text(response_data: dict[str, Any]) -> str:
    content = response_data.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def _request_translation_from_provider(
    provider: str,
    api_key: str,
    model: str,
    content: str,
    source_language: str,
    target_language: str,
) -> str:
    system_prompt = (
        "Translate Markdown while preserving Markdown structure, front matter, "
        "links, tables, code fences, inline code, math, and HTML. Return only the "
        "translated Markdown."
    )
    user_prompt = (
        f"Source language: {source_language or 'auto'}\n"
        f"Target language: {target_language}\n\n"
        "Markdown:\n"
        f"{content}"
    )
    base_url = _get_ai_base_url(provider)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if provider == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
        response = requests.post(
            f"{base_url}/messages",
            headers=headers,
            json={
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        translated = _extract_anthropic_text(response.json()).strip()
    else:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        translated = _extract_openai_compatible_text(response.json()).strip()

    if not translated:
        raise RuntimeError("AI provider returned an empty translation.")
    return translated


def get_ai_automation_task_templates() -> list[dict[str, Any]]:
    return [dict(item) for item in AI_AUTOMATION_TASK_TEMPLATES]


def load_ai_automation_logs(
    limit: int = AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES,
) -> list[dict[str, Any]]:
    if not AI_AUTOMATION_LOG_FILE_PATH.exists():
        return []
    try:
        with open(AI_AUTOMATION_LOG_FILE_PATH, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except Exception:
        return []
    logs = data if isinstance(data, list) else []
    return logs[-limit:] if limit > 0 else logs


def save_ai_automation_logs(log_entries: list[dict[str, Any]]) -> None:
    AI_AUTOMATION_LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_AUTOMATION_LOG_FILE_PATH, "w", encoding="utf-8") as file_obj:
        json.dump(
            log_entries[-AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES:], file_obj, indent=2
        )


def load_ai_chat_histories() -> list[dict[str, Any]]:
    if not AI_CHAT_HISTORY_FILE_PATH.exists():
        return []
    try:
        with open(AI_CHAT_HISTORY_FILE_PATH, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_ai_chat_histories(histories: list[dict[str, Any]]) -> None:
    AI_CHAT_HISTORY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_CHAT_HISTORY_FILE_PATH, "w", encoding="utf-8") as file_obj:
        json.dump(histories, file_obj, indent=2)


def _apply_markdown_formatting_rules(markdown_text: str) -> str:
    normalized = (markdown_text or "").replace("\r\n", "\n")
    lines = []
    for raw_line in normalized.split("\n"):
        line = raw_line.rstrip()
        line = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", line)
        line = re.sub(r"^(\s*)([-*+])(\S)", r"\1\2 \3", line)
        line = re.sub(r"^(\s*\d+\.)(\S)", r"\1 \2", line)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def _guess_code_language(code_block: str) -> str:
    sample = (code_block or "").strip()
    lowered = sample.lower()
    if "def " in sample or "import " in sample or "print(" in sample:
        return "python"
    if "function " in sample or "const " in sample or "=>" in sample:
        return "javascript"
    if lowered.startswith("{") and lowered.endswith("}"):
        return "json"
    return "text"


def _format_and_fix_code_blocks(markdown_text: str) -> str:
    normalized = (markdown_text or "").replace("\r\n", "\n")
    fence_count = len(re.findall(r"^\s*```", normalized, flags=re.MULTILINE))
    if fence_count % 2 == 1:
        return normalized.rstrip() + "\n```"
    return normalized


def _slugify_heading_text(text: str) -> str:
    plain = re.sub(r"[`*_~\[\](){}]", "", text or "").strip().lower()
    plain = re.sub(r"[^a-z0-9\s-]", "", plain)
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", plain)).strip("-")


def _generate_markdown_toc(markdown_text: str) -> str:
    toc_lines = []
    for line in (markdown_text or "").replace("\r\n", "\n").split("\n"):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        anchor = _slugify_heading_text(title)
        if anchor:
            toc_lines.append(f"{'  ' * max(0, level - 1)}- [{title}](#{anchor})")
    return "## Table of Contents\n\n" + "\n".join(toc_lines) + "\n" if toc_lines else ""


def _merge_toc_into_document(document_text: str, toc_text: str) -> str:
    doc = (document_text or "").replace("\r\n", "\n")
    toc = (toc_text or "").strip()
    if not toc:
        return doc
    replacement = toc.rstrip() + "\n\n"
    if doc.strip():
        return replacement + doc.lstrip("\n")
    return toc.rstrip() + "\n"


def _generate_lightweight_summary(markdown_text: str) -> str:
    if not (markdown_text or "").strip():
        return ""
    normalized = markdown_text.replace("\r\n", "\n")
    headings = []
    for line in normalized.split("\n"):
        match = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(1).strip())
        if len(headings) >= 5:
            break
    lead = ""
    for paragraph in re.split(r"\n\s*\n", normalized):
        paragraph = paragraph.strip()
        if paragraph and not paragraph.startswith("#"):
            lead = re.sub(r"\s+", " ", paragraph)
            break
    lines = ["## Summary"]
    if lead:
        lines.extend(["", f"- {lead[:240]}{'...' if len(lead) > 240 else ''}"])
    if headings:
        lines.extend(["", "- Main sections:"])
        lines.extend(f"  - {heading}" for heading in headings)
    return "\n".join(lines).strip() + "\n"


def build_ai_automation_fallback(
    user_message: str, document_text: str = "", selected_text: str = ""
) -> dict[str, Any] | None:
    lowered = (user_message or "").lower()
    slash_command = lowered.strip()
    if slash_command == "/summarize":
        lowered = "generate summary"
    elif slash_command == "/format":
        lowered = "format this section"
    elif slash_command == "/toc":
        lowered = "generate table of contents"
    elif slash_command == "/fix-code":
        lowered = "format code blocks and correct syntax"
    selection = selected_text if isinstance(selected_text, str) else ""
    document = document_text if isinstance(document_text, str) else ""
    target = selection if selection.strip() else document
    if not lowered.strip():
        return None
    if any(
        keyword in lowered
        for keyword in ("template", "task template", "automation template")
    ):
        template_lines = [
            f"- {item['id']}: {item['title']}"
            for item in get_ai_automation_task_templates()
        ]
        return {
            "assistant_message": "Available automation templates:\n"
            + "\n".join(template_lines),
            "proposed_action": {
                "type": "none",
                "content": "",
                "reason": "task_templates",
            },
            "used_provider": "local-fallback",
        }
    if any(keyword in lowered for keyword in ("table of contents", "toc", "目录")):
        toc = _generate_markdown_toc(document if document.strip() else target)
        if toc and not selection.strip():
            return {
                "assistant_message": toc,
                "proposed_action": {
                    "type": "replace_document",
                    "content": _merge_toc_into_document(document, toc),
                    "reason": "generate_toc_full_document",
                },
                "used_provider": "local-fallback",
            }
        if toc:
            return {
                "assistant_message": "Generated a table of contents. Review and apply if it matches your document structure.",
                "proposed_action": {
                    "type": "replace_selection",
                    "content": toc,
                    "reason": "generate_toc",
                },
                "used_provider": "local-fallback",
            }
    if "summary" in lowered or "summarize" in lowered or "总结" in lowered:
        summary = _generate_lightweight_summary(
            document if document.strip() else target
        )
        if not selection.strip() and summary:
            return {
                "assistant_message": summary,
                "proposed_action": {
                    "type": "replace_document",
                    "content": summary,
                    "reason": "generate_summary_full_document",
                },
                "used_provider": "local-fallback",
            }
        if not selection.strip():
            return {
                "assistant_message": "No document content available to summarize.",
                "proposed_action": {
                    "type": "none",
                    "content": "",
                    "reason": "no_content_for_summary",
                },
                "used_provider": "local-fallback",
            }
        if summary:
            return {
                "assistant_message": "Generated a concise summary based on current content.",
                "proposed_action": {
                    "type": "replace_selection",
                    "content": summary,
                    "reason": "generate_summary",
                },
                "used_provider": "local-fallback",
            }
    if (
        any(
            keyword in lowered
            for keyword in ("format code", "code block", "correct syntax", "fix code")
        )
        and target.strip()
    ):
        if not selection.strip():
            return {
                "assistant_message": "Select the code block you want to fix, then run this task again.",
                "proposed_action": {
                    "type": "none",
                    "content": "",
                    "reason": "selection_required_for_code_fix",
                },
                "used_provider": "local-fallback",
            }
        return {
            "assistant_message": "Prepared formatted code blocks and fixed common fence syntax issues.",
            "proposed_action": {
                "type": "replace_selection",
                "content": _format_and_fix_code_blocks(target),
                "reason": "fix_code_blocks",
            },
            "used_provider": "local-fallback",
        }
    if ("format" in lowered or "formatting" in lowered) and target.strip():
        action_type = "replace_selection" if selection.strip() else "replace_document"
        reason = "format_rules" if selection.strip() else "format_rules_full_document"
        return {
            "assistant_message": "Applied Markdown formatting normalization rules.",
            "proposed_action": {
                "type": action_type,
                "content": _apply_markdown_formatting_rules(target),
                "reason": reason,
            },
            "used_provider": "local-fallback",
        }
    return None


def request_ai_agent_response(
    message: str,
    document_text: str = "",
    selected_text: str = "",
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fallback = build_ai_automation_fallback(message, document_text, selected_text)
    if fallback:
        return fallback
    return {
        "assistant_message": "AI provider integration is configured, but no local fallback matched this request.",
        "proposed_action": {
            "type": "none",
            "content": "",
            "reason": "no_local_fallback",
        },
        "used_provider": "local-fallback",
    }


def translate_markdown_with_ai(
    content: str, source_language: str, target_language: str
) -> str:
    if not (content or "").strip():
        return ""

    provider = _get_current_ai_provider()
    api_key, _key_slot, env_var = _get_ai_api_key_for_provider(provider)
    if provider != "local" and not api_key:
        raise TranslationConfigError(
            "AI translation requires a configured provider API key.",
            provider_name=provider,
            env_var=env_var,
        )

    return _request_translation_from_provider(
        provider,
        api_key,
        get_ai_provider_model(provider),
        content,
        source_language,
        target_language,
    )
