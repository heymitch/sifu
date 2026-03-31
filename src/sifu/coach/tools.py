"""Tool awareness for Sifu coach — suggests automation tools for patterns."""

TOOL_REGISTRY = {
    "dev-browser": {
        "name": "dev-browser / BrowserMonkey",
        "description": "Browser automation via Playwright",
        "when": "Repeated browser click sequences (login, form fill, data extraction)",
        "indicators": ["click", "right_click"],
        "apps": ["Chrome", "Safari", "Firefox", "Arc", "Brave", "Edge"],
    },
    "computer-use": {
        "name": "Computer Use (MCP)",
        "description": "Cross-app automation via screen + mouse control",
        "when": "Cross-app workflows that can't be scripted via CLI",
        "indicators": ["app_switch", "click"],
        "apps": None,  # any app
    },
    "claude-cli": {
        "name": "Claude CLI",
        "description": "Text transformation and content generation",
        "when": "Text transformation, file processing, content generation patterns",
        "indicators": ["text_input", "command"],
        "apps": ["Ghostty", "Terminal", "iTerm2", "Warp"],
    },
    "applescript": {
        "name": "AppleScript / Shortcuts",
        "description": "macOS-native app automation",
        "when": "macOS-specific app automation (Finder, Mail, Calendar)",
        "indicators": ["click", "shortcut"],
        "apps": ["Finder", "Mail", "Calendar", "Notes", "Reminders", "Preview"],
    },
    "shell": {
        "name": "Shell aliases/scripts",
        "description": "Terminal command automation",
        "when": "Repeated terminal command sequences",
        "indicators": ["command"],
        "apps": ["Ghostty", "Terminal", "iTerm2", "Warp", "Alacritty", "kitty"],
    },
}


def suggest_tools(events) -> list[dict]:
    """Analyze events and suggest appropriate automation tools."""
    findings = []
    from collections import Counter

    # Group events by app
    by_app: dict[str, list] = {}
    for e in events:
        app = e["app"] or "Unknown"
        by_app.setdefault(app, []).append(e)

    for tool_id, tool in TOOL_REGISTRY.items():
        matching_apps = tool["apps"]

        for app, app_events in by_app.items():
            if matching_apps and app not in matching_apps:
                continue

            # Count matching event types
            matching = [e for e in app_events if e["type"] in tool["indicators"]]
            if len(matching) >= 10:
                findings.append({
                    "category": "tools",
                    "message": (
                        f"{app}: {len(matching)} actions could use {tool['name']}"
                        f" — {tool['when']}"
                    ),
                    "count": len(matching),
                    "severity": "medium",
                    "tool": tool_id,
                })

    return findings
