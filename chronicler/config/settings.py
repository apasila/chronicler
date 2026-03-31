from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import toml


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


@dataclass
class LoggingConfig:
    default_mode: str = "debounced"
    mode: str | None = None
    session_gap_minutes: int = 30
    debounce_seconds: int = 10

    @property
    def effective_mode(self) -> str:
        return self.mode or self.default_mode


@dataclass
class ModelsConfig:
    tier: str = "cloud"
    workhorse: str = "groq/llama-3.3-70b-versatile"
    premium: str = "groq/llama-3.3-70b-versatile"


@dataclass
class GroqConfig:
    api_key: str = ""


@dataclass
class OllamaConfig:
    enabled: bool = False
    base_url: str = "http://localhost:11434"
    workhorse_model: str = "phi4"
    premium_model: str = "phi4"


@dataclass
class CustomProviderConfig:
    enabled: bool = False
    base_url: str = "http://localhost:8080/v1"
    api_key: str = ""
    model: str = "local-model"


DEFAULT_IGNORE_PATTERNS: list[str] = [
    "node_modules/**",
    ".git/**",
    "*.lock",
    "*.log",
    "dist/**",
    "build/**",
    ".env",
    ".env.*",
    "__pycache__/**",
    ".DS_Store",
    "*.pyc",
    ".pytest_cache/**",
    ".next/**",
    "*.tsbuildinfo",
    ".venv/**",
    "venv/**",
    ".mypy_cache/**",
    "coverage/**",
    ".coverage",
    "*.min.js",
    "*.min.css",
]


@dataclass
class IgnoreConfig:
    patterns: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_PATTERNS))


@dataclass
class StorageConfig:
    db_path: str = "~/.config/chronicler/chronicler.db"
    max_db_size_mb: int = 500


@dataclass
class ProjectConfig:
    name: str = ""
    framework: str | None = None
    languages: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass
class Config:
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    groq: GroqConfig = field(default_factory=GroqConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    custom: CustomProviderConfig = field(default_factory=CustomProviderConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    project: ProjectConfig = field(default_factory=ProjectConfig)


def _dict_to_config(d: dict) -> Config:
    cfg = Config()
    if logging := d.get("logging"):
        fields = LoggingConfig.__dataclass_fields__
        cfg.logging = LoggingConfig(**{k: v for k, v in logging.items() if k in fields})
    if models := d.get("models"):
        cfg.models = ModelsConfig(**{k: v for k, v in models.items()
                                     if k in ModelsConfig.__dataclass_fields__})
    if groq := d.get("groq"):
        cfg.groq = GroqConfig(**{k: v for k, v in groq.items()
                                  if k in GroqConfig.__dataclass_fields__})
    if ollama := d.get("ollama"):
        cfg.ollama = OllamaConfig(**{k: v for k, v in ollama.items()
                                     if k in OllamaConfig.__dataclass_fields__})
    if custom := d.get("custom"):
        cfg.custom = CustomProviderConfig(**{k: v for k, v in custom.items()
                                             if k in CustomProviderConfig.__dataclass_fields__})
    if ignore := d.get("ignore"):
        user_patterns = ignore.get("global_patterns", ignore.get("patterns", []))
        # Merge user patterns with defaults (user patterns take precedence, no duplicates)
        merged = list(DEFAULT_IGNORE_PATTERNS)
        for p in user_patterns:
            if p not in merged:
                merged.append(p)
        cfg.ignore = IgnoreConfig(patterns=merged)
    if storage := d.get("storage"):
        cfg.storage = StorageConfig(**{k: v for k, v in storage.items()
                                       if k in StorageConfig.__dataclass_fields__})
    if project := d.get("project"):
        cfg.project = ProjectConfig(**{k: v for k, v in project.items()
                                       if k in ProjectConfig.__dataclass_fields__})
    return cfg


def load_config(project_path: str, global_config_dir: str | None = None) -> Config:
    """Three-tier cascade: global defaults → project overrides → environment."""
    if global_config_dir is None:
        global_config_dir = str(Path.home() / ".config" / "chronicler")

    raw: dict[str, Any] = {}
    global_toml = Path(global_config_dir) / "config.toml"
    if global_toml.exists():
        raw = toml.load(str(global_toml))

    project_toml = Path(project_path) / ".chronicler" / "config.toml"
    if project_toml.exists():
        project_raw = toml.load(str(project_toml))
        # Merge ignore patterns additively
        global_patterns = raw.get("ignore", {}).get("global_patterns", [])
        project_patterns = project_raw.get("ignore", {}).get("patterns", [])
        if project_raw.get("ignore") is None:
            project_raw["ignore"] = {}
        project_raw["ignore"]["global_patterns"] = list(set(global_patterns + project_patterns))
        raw = _deep_merge(raw, project_raw)

    config = _dict_to_config(raw)

    # Env var is a fallback only — config file key takes priority
    if not config.groq.api_key:
        if api_key := os.environ.get("GROQ_API_KEY"):
            config.groq.api_key = api_key

    if config.custom.enabled and config.custom.api_key:
        os.environ["OPENAI_API_KEY"] = config.custom.api_key

    return config
