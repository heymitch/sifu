"""Configuration system for Sifu."""

import json
from pathlib import Path
from typing import Any

SIFU_DIR = Path.home() / ".sifu"
CONFIG_PATH = SIFU_DIR / "config.json"

DEFAULT_CONFIG = {
    "screenshot_budget_mb": 1024,
    "screenshot_min_interval_s": 2.0,
    "screenshot_format": "jpeg",
    "screenshot_quality": 80,
    "idle_timeout_s": 300,
    "session_gap_s": 30,
    "ignore_apps": [
        "1Password", "Bitwarden", "KeyChain Access",
        "loginwindow", "ScreenSaverEngine",
    ],
    "sensitive_purge_minutes": 5,
    "output_dir": str(SIFU_DIR / "output"),
    "sops_dir": str(SIFU_DIR / "output" / "sops"),
    "automations_dir": str(SIFU_DIR / "automations"),
    "capabilities_dir": str(SIFU_DIR / "capabilities.d"),
    "workflows_dir": str(SIFU_DIR / "output" / "workflows"),
    "editor": None,  # App name (e.g. "Sublime Text", "VS Code"). None = system default.
}


def load_config() -> dict:
    """Load config, merging user overrides with defaults."""
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_config = json.load(f)
        return {**DEFAULT_CONFIG, **user_config}
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Write config to disk."""
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set_value(key: str, value: Any):
    """Set a config value, coercing type to match the default."""
    config = load_config()
    if key in DEFAULT_CONFIG:
        default_val = DEFAULT_CONFIG[key]
        if isinstance(default_val, int):
            value = int(value)
        elif isinstance(default_val, float):
            value = float(value)
        elif isinstance(default_val, bool):
            value = str(value).lower() in ("true", "1", "yes")
        elif isinstance(default_val, list) and isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
    config[key] = value
    save_config(config)


def handle_config(key=None, value=None):
    """Show or update config. Called from CLI."""
    import click

    if key and value:
        set_value(key, value)
        click.echo(f"Set {key} = {value}")
    elif key:
        val = get(key)
        if val is not None:
            click.echo(f"{key} = {val}")
        else:
            click.echo(f"Unknown config key: {key}")
    else:
        config = load_config()
        for k, v in sorted(config.items()):
            click.echo(f"  {k}: {v}")


def add_ignore_app(app: str):
    """Add an app to the ignore list. Called from CLI."""
    import click

    config = load_config()
    apps = config.get("ignore_apps", [])
    if app not in apps:
        apps.append(app)
        config["ignore_apps"] = apps
        save_config(config)
        click.echo(f"Added '{app}' to ignore list.")
    else:
        click.echo(f"'{app}' is already in ignore list.")
