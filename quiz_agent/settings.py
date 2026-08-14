from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


def _pick(config: Optional[Mapping[str, Any]], key: str, default: Any = None) -> Any:
    if config is not None:
        value = config.get(key)
        if value not in (None, ""):
            return value
    import os

    env_value = os.environ.get(key)
    if env_value not in (None, ""):
        return env_value
    return default


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class AgentSettings:
    api_key: str
    llm_base_url: str = "https://tokenhub.tencentmaas.com/v1"
    llm_model: str = "hy3"
    search_api_key: Optional[str] = None
    search_api_url: str = "https://api.wsa.cloud.tencent.com/SearchPro"
    search_mode: Optional[int] = None
    search_cnt: int = 20
    search_max_items: int = 10
    search_passage_chars: int = 800
    search_site: Optional[str] = "easonfans.com"
    tencent_secret_id: Optional[str] = None
    tencent_secret_key: Optional[str] = None
    search_backend: str = "auto"
    max_turns: int = 12
    search_web_rounds: int = 3

    @classmethod
    def from_mapping(cls, config: Optional[Mapping[str, Any]] = None) -> "AgentSettings":
        site = _pick(config, "SEARCH_SITE", "easonfans.com")
        if site is not None:
            site = str(site).strip() or None
        backend = str(_pick(config, "SEARCH_BACKEND", "auto") or "auto").strip().lower()
        return cls(
            api_key=str(_pick(config, "API_KEY", "") or ""),
            llm_base_url=str(
                _pick(config, "LLM_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
            ),
            llm_model=str(_pick(config, "LLM_MODEL", "hy3")),
            search_api_key=_pick(config, "SEARCH_API_KEY"),
            search_api_url=str(
                _pick(config, "SEARCH_API_URL", "https://api.wsa.cloud.tencent.com/SearchPro")
            ),
            search_mode=_as_optional_int(_pick(config, "SEARCH_MODE")),
            search_cnt=_as_int(_pick(config, "AGENT_SEARCH_ITEMS"), 10),
            search_max_items=_as_int(_pick(config, "AGENT_SEARCH_ITEMS"), 10),
            search_passage_chars=_as_int(_pick(config, "SEARCH_PASSAGE_CHARS"), 800),
            search_site=site,
            tencent_secret_id=_pick(config, "TENCENTCLOUD_SECRET_ID"),
            tencent_secret_key=_pick(config, "TENCENTCLOUD_SECRET_KEY"),
            search_backend=backend,
            max_turns=_as_int(_pick(config, "AGENT_MAX_TURNS"), 12),
            search_web_rounds=_as_int(_pick(config, "SEARCH_WEB_ROUNDS"), 3),
        )


_settings: Optional[AgentSettings] = None


def configure(settings: AgentSettings) -> None:
    global _settings
    _settings = settings


def get_settings() -> AgentSettings:
    if _settings is None:
        raise RuntimeError("quiz_agent.configure() 尚未调用")
    return _settings
