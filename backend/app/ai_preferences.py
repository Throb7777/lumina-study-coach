from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AppSetting

CODEX_DEFAULT_MODEL = "gpt-5.5"
CODEX_DEFAULT_REASONING_EFFORT = "medium"
GEMINI_DEFAULT_MODEL = "Gemini 3.5 Flash"
GEMINI_DEFAULT_REASONING_EFFORT = "high"

CODEX_MODEL_SETTING = "codex_model"
CODEX_REASONING_EFFORT_SETTING = "codex_reasoning_effort"
GEMINI_MODEL_SETTING = "gemini_model"
GEMINI_REASONING_EFFORT_SETTING = "gemini_reasoning_effort"


@dataclass(frozen=True)
class AiPreference:
    model: str
    reasoning_effort: str


def _setting(session: Session, key: str, default: str) -> str:
    setting = session.get(AppSetting, key)
    value = setting.value.strip() if setting is not None else ""
    return value or default


def codex_preference(session: Session) -> AiPreference:
    return AiPreference(
        model=_setting(session, CODEX_MODEL_SETTING, CODEX_DEFAULT_MODEL),
        reasoning_effort=_setting(
            session,
            CODEX_REASONING_EFFORT_SETTING,
            CODEX_DEFAULT_REASONING_EFFORT,
        ),
    )


def gemini_preference(session: Session) -> AiPreference:
    return AiPreference(
        model=_setting(session, GEMINI_MODEL_SETTING, GEMINI_DEFAULT_MODEL),
        reasoning_effort=_setting(
            session,
            GEMINI_REASONING_EFFORT_SETTING,
            GEMINI_DEFAULT_REASONING_EFFORT,
        ),
    )


def gemini_cli_model(model: str, reasoning_effort: str) -> str:
    normalized_model = model.strip().lower()
    normalized_model = normalized_model.removesuffix(" (low)")
    normalized_model = normalized_model.removesuffix(" (medium)")
    normalized_model = normalized_model.removesuffix(" (high)")
    normalized_model = "-".join(normalized_model.split())
    for effort in ("low", "medium", "high"):
        normalized_model = normalized_model.removesuffix(f"-{effort}")
    return f"{normalized_model}-{reasoning_effort.strip().lower()}"


def save_preference(
    session: Session,
    *,
    provider: str,
    model: str,
    reasoning_effort: str,
) -> AiPreference:
    keys = (
        (CODEX_MODEL_SETTING, CODEX_REASONING_EFFORT_SETTING)
        if provider == "codex"
        else (GEMINI_MODEL_SETTING, GEMINI_REASONING_EFFORT_SETTING)
    )
    for key, value in zip(keys, (model, reasoning_effort), strict=True):
        setting = session.get(AppSetting, key)
        if setting is None:
            session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
    session.commit()
    return AiPreference(model=model, reasoning_effort=reasoning_effort)
