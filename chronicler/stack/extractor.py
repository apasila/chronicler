from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import toml

from chronicler.stack.schema import StackEntry, TechStack, STACK_CATEGORIES

_SERVICE_PATTERNS = {
    "stripe": "stripe", "sendgrid": "sendgrid", "twilio": "twilio",
    "mailgun": "mailgun", "aws": "aws", "gcp": "gcp", "azure": "azure",
    "openai": "openai", "anthropic": "anthropic", "groq": "groq",
    "gemini": "gemini", "sentry": "sentry", "datadog": "datadog",
    "segment": "segment", "mixpanel": "mixpanel", "amplitude": "amplitude",
    "pusher": "pusher", "cloudinary": "cloudinary", "algolia": "algolia",
    "supabase": "supabase", "firebase": "firebase", "mongo": "mongodb",
    "redis": "redis", "postgres": "postgresql", "mysql": "mysql",
    "planetscale": "planetscale", "neon": "neon", "vercel": "vercel",
    "netlify": "netlify", "github": "github", "slack": "slack",
    "discord": "discord", "telegram": "telegram", "twitch": "twitch",
    "spotify": "spotify", "google": "google", "facebook": "facebook",
    "twitter": "twitter", "paypal": "paypal", "braintree": "braintree",
    "fish_audio": "fish-audio", "kokoro": "kokoro", "polygon": "polygon",
}

_MANIFEST_GLOBS = [
    "package.json", "pyproject.toml", "requirements.txt", "Cargo.toml",
    "go.mod", "tsconfig.json", "tailwind.config.js", "tailwind.config.ts",
    "tailwind.config.mjs", ".env.example",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_manifests(project_path: Path) -> str:
    """SHA-256 of all manifest file contents, sorted by name for stability."""
    h = hashlib.sha256()
    found = []
    for glob in _MANIFEST_GLOBS:
        for p in sorted(project_path.glob(glob)):
            if p.is_file():
                found.append(p)
    for p in sorted(found, key=lambda x: x.name):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _entry(key: str, category: str, value: str, source: str) -> StackEntry:
    now = _now()
    return StackEntry(
        key=key, category=category, value=value,
        source=source, confidence=1.0,
        detected_at=now, last_verified=now,
    )


def _parse_package_json(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return entries
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in (data.get(section) or {}).items():
            entries.append(_entry(name, "library", str(version), "package.json"))
    engines = data.get("engines") or {}
    for runtime, version in engines.items():
        entries.append(_entry(runtime, "runtime", str(version), "package.json"))
    return entries


def _parse_tsconfig(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return entries
    opts = data.get("compilerOptions") or {}
    if "target" in opts:
        entries.append(_entry("typescript-target", "language", str(opts["target"]), "tsconfig.json"))
    return entries


def _parse_pyproject(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = toml.loads(path.read_text())
    except Exception:
        return entries
    deps = (data.get("project") or {}).get("dependencies") or []
    for dep in deps:
        name = re.split(r"[><=!~\s\[]", dep)[0].strip()
        entries.append(_entry(name, "library", dep, "pyproject.toml"))
    return entries


def _parse_requirements(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[><=!~\s\[]", line)[0].strip()
        if name:
            entries.append(_entry(name, "library", line, "requirements.txt"))
    return entries


def _parse_cargo(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = toml.loads(path.read_text())
    except Exception:
        return entries
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, spec in (data.get(section) or {}).items():
            version = spec if isinstance(spec, str) else (spec.get("version") or "")
            entries.append(_entry(name, "library", version, "Cargo.toml"))
    return entries


def _parse_go_mod(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("require ") and " " in line:
            parts = line.split()
            if len(parts) >= 3:
                entries.append(_entry(parts[1], "library", parts[2], "go.mod"))
        elif not line.startswith("//") and not line.startswith("module") and not line.startswith("go "):
            parts = line.split()
            if len(parts) == 2 and "/" in parts[0]:
                entries.append(_entry(parts[0], "library", parts[1], "go.mod"))
    return entries


def _parse_tailwind(path: Path) -> list[StackEntry]:
    """Extract color hex values from tailwind config using regex (no JS eval)."""
    entries: list[StackEntry] = []
    text = path.read_text()
    for match in re.finditer(r"'#([0-9a-fA-F]{3,8})'|\"#([0-9a-fA-F]{3,8})\"", text):
        color = "#" + (match.group(1) or match.group(2))
        entries.append(_entry(color, "color", color, path.name))
    return entries


def _parse_env_example(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=")[0].lower()
        for pattern, service in _SERVICE_PATTERNS.items():
            if pattern in key and service not in seen:
                seen.add(service)
                entries.append(_entry(service, "service", "detected", ".env.example"))
                break
    return entries


def extract_stack(project_path: Path) -> TechStack:
    """Run Stage 1: deterministic manifest parsing. Returns a TechStack."""
    entries: list[StackEntry] = []
    parsers = [
        ("package.json",      _parse_package_json),
        ("tsconfig.json",     _parse_tsconfig),
        ("pyproject.toml",    _parse_pyproject),
        ("requirements.txt",  _parse_requirements),
        ("Cargo.toml",        _parse_cargo),
        ("go.mod",            _parse_go_mod),
        (".env.example",      _parse_env_example),
    ]
    for filename, parser in parsers:
        p = project_path / filename
        if p.exists():
            entries.extend(parser(p))
    for tw_name in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs"):
        p = project_path / tw_name
        if p.exists():
            entries.extend(_parse_tailwind(p))
            break
    return TechStack(
        generated_at=datetime.now(timezone.utc),
        manifest_hash=_hash_manifests(project_path),
        entries=entries,
        constraints=[],
    )
