"""Capability discovery — scans for available automation tools on the machine."""

import importlib.util
import json
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

KNOWN_CLI_TOOLS = {
    "git": {
        "description": "Git version control",
        "matches": [{"command_contains": "git"}],
        "actions": ["status", "add", "commit", "push", "pull", "diff", "log", "branch"],
    },
    "vercel": {
        "description": "Vercel deployment CLI",
        "matches": [{"command_contains": "vercel"}],
        "actions": ["deploy", "dev", "env", "domains"],
    },
    "gh": {
        "description": "GitHub CLI",
        "matches": [{"command_contains": "gh"}],
        "actions": ["pr", "issue", "repo", "run", "api"],
    },
    "docker": {
        "description": "Docker container management",
        "matches": [{"command_contains": "docker"}],
        "actions": ["build", "run", "push", "compose"],
    },
    "npm": {
        "description": "Node package manager",
        "matches": [{"command_contains": "npm"}],
        "actions": ["install", "run", "publish", "test"],
    },
    "node": {
        "description": "Node.js runtime",
        "matches": [{"command_contains": "node"}],
        "actions": ["run"],
    },
    "python3": {
        "description": "Python runtime",
        "matches": [{"command_contains": "python"}],
        "actions": ["run"],
    },
    "aws": {
        "description": "AWS CLI",
        "matches": [{"command_contains": "aws"}],
        "actions": ["s3", "lambda", "ec2", "iam"],
    },
    "gcloud": {
        "description": "Google Cloud CLI",
        "matches": [{"command_contains": "gcloud"}],
        "actions": ["compute", "functions", "run"],
    },
    "curl": {
        "description": "HTTP client",
        "matches": [{"command_contains": "curl"}],
        "actions": ["request"],
    },
    "supabase": {
        "description": "Supabase CLI",
        "matches": [{"command_contains": "supabase"}],
        "actions": ["db", "functions", "migration"],
    },
}


@dataclass
class Capability:
    name: str
    type: str  # cli, mcp, browser, applescript, custom
    description: str
    matches: list[dict] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    source: str = "builtin"


def discover_cli_tools() -> list[Capability]:
    """Check shutil.which for each known CLI tool and return available ones."""
    capabilities = []
    for tool_name, tool_info in KNOWN_CLI_TOOLS.items():
        if shutil.which(tool_name) is not None:
            capabilities.append(
                Capability(
                    name=tool_name,
                    type="cli",
                    description=tool_info["description"],
                    matches=tool_info["matches"],
                    actions=tool_info["actions"],
                    source="builtin",
                )
            )
    return capabilities


def discover_mcp_servers(search_paths: list[Path] | None = None) -> list[Capability]:
    """Read .mcp.json files from configurable search paths and return capabilities."""
    if search_paths is None:
        search_paths = [Path.home(), Path.cwd()]

    capabilities = []
    for search_path in search_paths:
        mcp_file = search_path / ".mcp.json"
        if not mcp_file.exists():
            continue
        try:
            with open(mcp_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        servers = data.get("mcpServers", {})
        for server_name, server_config in servers.items():
            capabilities.append(
                Capability(
                    name=server_name,
                    type="mcp",
                    description=server_config.get("description", f"MCP server: {server_name}"),
                    matches=server_config.get("matches", [{"command_contains": server_name}]),
                    actions=server_config.get("actions", []),
                    source=str(mcp_file),
                )
            )

    return capabilities


def load_capability_extensions(capabilities_dir: Path | None = None) -> list[Capability]:
    """Load YAML capability extension files from capabilities.d/ directory."""
    if capabilities_dir is None:
        capabilities_dir = Path.home() / ".sifu" / "capabilities.d"

    if not capabilities_dir.exists() or not capabilities_dir.is_dir():
        return []

    capabilities = []
    yaml_files = list(capabilities_dir.glob("*.yaml")) + list(capabilities_dir.glob("*.yml"))

    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue
            name = data.get("name")
            if not name:
                continue
            capabilities.append(
                Capability(
                    name=name,
                    type=data.get("type", "custom"),
                    description=data.get("description", ""),
                    matches=data.get("matches", []),
                    actions=data.get("actions", []),
                    source=str(yaml_file),
                )
            )
        except (yaml.YAMLError, OSError, KeyError):
            continue

    return capabilities


def _discover_browser_automation() -> list[Capability]:
    """Check for playwright or selenium and return browser automation capability if found."""
    capabilities = []

    if importlib.util.find_spec("playwright") is not None:
        capabilities.append(
            Capability(
                name="playwright",
                type="browser",
                description="Playwright browser automation",
                matches=[{"app_contains": "browser"}, {"command_contains": "playwright"}],
                actions=["navigate", "click", "type", "screenshot", "wait"],
                source="builtin",
            )
        )

    if importlib.util.find_spec("selenium") is not None:
        capabilities.append(
            Capability(
                name="selenium",
                type="browser",
                description="Selenium browser automation",
                matches=[{"app_contains": "browser"}, {"command_contains": "selenium"}],
                actions=["navigate", "click", "type", "screenshot", "wait"],
                source="builtin",
            )
        )

    return capabilities


def _discover_applescript() -> list[Capability]:
    """Return AppleScript capability if running on macOS."""
    if platform.system() != "Darwin":
        return []

    return [
        Capability(
            name="applescript",
            type="applescript",
            description="AppleScript macOS automation",
            matches=[{"app_contains": "finder"}, {"app_contains": "system events"}],
            actions=["run", "tell", "keystroke", "click"],
            source="builtin",
        )
    ]


def discover_capabilities(
    capabilities_dir: Path | None = None,
    mcp_search_paths: list[Path] | None = None,
) -> list[Capability]:
    """Combine all discovery sources into a deduplicated capability list.

    Extensions override builtins when names conflict.
    """
    # Gather builtins first
    builtins: list[Capability] = []
    builtins.extend(discover_cli_tools())
    builtins.extend(discover_mcp_servers(mcp_search_paths))
    builtins.extend(_discover_browser_automation())
    builtins.extend(_discover_applescript())

    # Load extensions
    extensions = load_capability_extensions(capabilities_dir)

    # Build final map — extensions win on name collision
    capability_map: dict[str, Capability] = {}
    for cap in builtins:
        capability_map[cap.name] = cap
    for cap in extensions:
        capability_map[cap.name] = cap  # override builtins

    return list(capability_map.values())
