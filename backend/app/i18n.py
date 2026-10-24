from typing import Optional


DEFAULT_LANGUAGE = "en"

MESSAGES = {
    "en": {
        "email_already_registered": "Email already registered",
        "invalid_credentials": "Invalid credentials",
        "could_not_validate_credentials": "Could not validate credentials",
        "goal_not_found": "Goal not found",
        "task_not_found": "Task not found",
        "not_authorized": "Not authorized",
        "ai_not_configured": "AI analysis is not configured. Set OPENROUTER_API_KEY.",
        "ai_provider_http_error": "AI provider request failed with status {status}.",
        "ai_provider_unreachable": "AI provider could not be reached.",
        "ai_provider_invalid_response": "AI provider returned an invalid response.",
        "ai_provider_invalid_analysis": "AI provider returned an invalid goal analysis.",
    },
    "ru": {
        "email_already_registered": "Электронная почта уже зарегистрирована",
        "invalid_credentials": "Неверные учётные данные",
        "could_not_validate_credentials": "Не удалось проверить учётные данные",
        "goal_not_found": "Цель не найдена",
        "task_not_found": "Задача не найдена",
        "not_authorized": "Доступ запрещён",
        "ai_not_configured": "AI-анализ не настроен. Укажите OPENROUTER_API_KEY.",
        "ai_provider_http_error": "Запрос к AI-провайдеру завершился со статусом {status}.",
        "ai_provider_unreachable": "Не удалось связаться с AI-провайдером.",
        "ai_provider_invalid_response": "AI-провайдер вернул некорректный ответ.",
        "ai_provider_invalid_analysis": "AI-провайдер вернул некорректный анализ цели.",
    },
}


def resolve_language(accept_language: Optional[str]) -> str:
    """Pick the best supported language from an Accept-Language header."""
    if not isinstance(accept_language, str) or not accept_language:
        return DEFAULT_LANGUAGE

    preferences = []
    for index, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        language = piece.split(";")[0].strip().lower()
        quality = 1.0
        for parameter in piece.split(";")[1:]:
            parameter = parameter.strip()
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        preferences.append((quality, index, language))

    for _, _, language in sorted(preferences, key=lambda item: (-item[0], item[1])):
        base = language.split("-")[0]
        if base in MESSAGES:
            return base

    return DEFAULT_LANGUAGE


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Translate a message key, falling back to English when missing."""
    template = MESSAGES.get(lang, {}).get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
