"""Tests for Sifu capability discovery module."""

import json
from pathlib import Path

import pytest

from sifu.classifier.discovery import (
    Capability,
    discover_capabilities,
    discover_cli_tools,
    discover_mcp_servers,
    load_capability_extensions,
)


class TestCapabilityDataclass:
    def test_required_fields(self):
        cap = Capability(name="git", type="cli", description="Git version control")
        assert cap.name == "git"
        assert cap.type == "cli"
        assert cap.description == "Git version control"

    def test_default_fields(self):
        cap = Capability(name="git", type="cli", description="Git version control")
        assert cap.matches == []
        assert cap.actions == []
        assert cap.source == "builtin"

    def test_custom_fields(self):
        cap = Capability(
            name="git",
            type="cli",
            description="Git version control",
            matches=[{"command_contains": "git"}],
            actions=["status", "commit"],
            source="/path/to/.mcp.json",
        )
        assert cap.matches == [{"command_contains": "git"}]
        assert cap.actions == ["status", "commit"]
        assert cap.source == "/path/to/.mcp.json"

    def test_mutable_defaults_are_independent(self):
        cap1 = Capability(name="a", type="cli", description="A")
        cap2 = Capability(name="b", type="cli", description="B")
        cap1.matches.append({"x": "y"})
        assert cap2.matches == []


class TestDiscoverCliTools:
    def test_git_found(self):
        """git should exist on any dev machine."""
        tools = discover_cli_tools()
        names = [c.name for c in tools]
        assert "git" in names

    def test_returns_capability_objects(self):
        tools = discover_cli_tools()
        assert all(isinstance(c, Capability) for c in tools)

    def test_cli_type_and_builtin_source(self):
        tools = discover_cli_tools()
        for cap in tools:
            assert cap.type == "cli"
            assert cap.source == "builtin"

    def test_missing_tools_not_included(self):
        """Tools that don't exist on PATH should not appear."""
        tools = discover_cli_tools()
        names = [c.name for c in tools]
        # These are unlikely to exist on a standard dev machine
        assert "supabase_nonexistent_tool_xyz" not in names

    def test_git_has_expected_actions(self):
        tools = discover_cli_tools()
        git_caps = [c for c in tools if c.name == "git"]
        assert len(git_caps) == 1
        assert "commit" in git_caps[0].actions
        assert "push" in git_caps[0].actions

    def test_git_has_matches(self):
        tools = discover_cli_tools()
        git_cap = next(c for c in tools if c.name == "git")
        assert len(git_cap.matches) > 0
        assert git_cap.matches[0].get("command_contains") == "git"


class TestDiscoverMcpServers:
    def test_reads_mcp_json(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "framer": {
                    "description": "Framer design tool",
                    "actions": ["design", "publish"],
                }
            }
        }))
        caps = discover_mcp_servers(search_paths=[tmp_path])
        assert len(caps) == 1
        assert caps[0].name == "framer"
        assert caps[0].type == "mcp"
        assert caps[0].description == "Framer design tool"
        assert caps[0].actions == ["design", "publish"]
        assert str(mcp_file) == caps[0].source

    def test_no_mcp_json_returns_empty(self, tmp_path):
        caps = discover_mcp_servers(search_paths=[tmp_path])
        assert caps == []

    def test_multiple_servers_in_one_file(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "tool_a": {"description": "Tool A"},
                "tool_b": {"description": "Tool B"},
            }
        }))
        caps = discover_mcp_servers(search_paths=[tmp_path])
        names = [c.name for c in caps]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_invalid_json_skipped(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text("{ not valid json }")
        caps = discover_mcp_servers(search_paths=[tmp_path])
        assert caps == []

    def test_missing_description_gets_default(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "myserver": {}
            }
        }))
        caps = discover_mcp_servers(search_paths=[tmp_path])
        assert len(caps) == 1
        assert "myserver" in caps[0].description

    def test_multiple_search_paths(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / ".mcp.json").write_text(json.dumps({
            "mcpServers": {"tool_a": {"description": "A"}}
        }))
        (dir_b / ".mcp.json").write_text(json.dumps({
            "mcpServers": {"tool_b": {"description": "B"}}
        }))
        caps = discover_mcp_servers(search_paths=[dir_a, dir_b])
        names = [c.name for c in caps]
        assert "tool_a" in names
        assert "tool_b" in names


class TestLoadCapabilityExtensions:
    def test_loads_yaml_file(self, tmp_path):
        cap_file = tmp_path / "myapp.yaml"
        cap_file.write_text(
            "name: myapp\n"
            "type: custom\n"
            "description: My custom app\n"
            "actions:\n"
            "  - open\n"
            "  - close\n"
            "matches:\n"
            "  - app_contains: myapp\n"
        )
        caps = load_capability_extensions(tmp_path)
        assert len(caps) == 1
        assert caps[0].name == "myapp"
        assert caps[0].type == "custom"
        assert caps[0].description == "My custom app"
        assert "open" in caps[0].actions
        assert caps[0].source == str(cap_file)

    def test_loads_yml_extension(self, tmp_path):
        cap_file = tmp_path / "myapp.yml"
        cap_file.write_text("name: myapp\ntype: custom\ndescription: My App\n")
        caps = load_capability_extensions(tmp_path)
        assert len(caps) == 1
        assert caps[0].name == "myapp"

    def test_invalid_yaml_skipped_gracefully(self, tmp_path):
        (tmp_path / "good.yaml").write_text("name: good\ntype: custom\ndescription: Good\n")
        (tmp_path / "bad.yaml").write_text(": : : invalid yaml :::\n\t\tbad indent")
        caps = load_capability_extensions(tmp_path)
        # Only the good file should load; bad file skipped
        names = [c.name for c in caps]
        assert "good" in names

    def test_missing_name_skipped(self, tmp_path):
        (tmp_path / "no_name.yaml").write_text("type: custom\ndescription: No name\n")
        caps = load_capability_extensions(tmp_path)
        assert caps == []

    def test_empty_dir_returns_empty(self, tmp_path):
        caps = load_capability_extensions(tmp_path)
        assert caps == []

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        caps = load_capability_extensions(tmp_path / "does_not_exist")
        assert caps == []

    def test_source_set_to_file_path(self, tmp_path):
        cap_file = tmp_path / "tool.yaml"
        cap_file.write_text("name: tool\ntype: custom\ndescription: A tool\n")
        caps = load_capability_extensions(tmp_path)
        assert caps[0].source == str(cap_file)

    def test_multiple_yaml_files(self, tmp_path):
        (tmp_path / "alpha.yaml").write_text("name: alpha\ntype: custom\ndescription: Alpha\n")
        (tmp_path / "beta.yaml").write_text("name: beta\ntype: custom\ndescription: Beta\n")
        caps = load_capability_extensions(tmp_path)
        names = [c.name for c in caps]
        assert "alpha" in names
        assert "beta" in names


class TestDiscoverCapabilities:
    def test_combines_all_sources(self, tmp_path):
        # Set up an MCP file
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / ".mcp.json").write_text(json.dumps({
            "mcpServers": {"test_mcp": {"description": "Test MCP server"}}
        }))

        # Set up an extension
        ext_dir = tmp_path / "ext"
        ext_dir.mkdir()
        (ext_dir / "custom.yaml").write_text(
            "name: custom_tool\ntype: custom\ndescription: Custom\n"
        )

        caps = discover_capabilities(
            capabilities_dir=ext_dir,
            mcp_search_paths=[mcp_dir],
        )
        names = [c.name for c in caps]
        assert "git" in names          # from CLI discovery
        assert "test_mcp" in names     # from MCP discovery
        assert "custom_tool" in names  # from extension

    def test_no_duplicates(self, tmp_path):
        caps = discover_capabilities(
            capabilities_dir=tmp_path,
            mcp_search_paths=[tmp_path],
        )
        names = [c.name for c in caps]
        assert len(names) == len(set(names))

    def test_extensions_override_builtins(self, tmp_path):
        """An extension with the same name as a CLI tool should win."""
        (tmp_path / "git.yaml").write_text(
            "name: git\n"
            "type: custom\n"
            "description: Overridden git\n"
            "actions:\n"
            "  - custom_action\n"
        )
        caps = discover_capabilities(
            capabilities_dir=tmp_path,
            mcp_search_paths=[],
        )
        git_caps = [c for c in caps if c.name == "git"]
        assert len(git_caps) == 1
        assert git_caps[0].type == "custom"
        assert git_caps[0].description == "Overridden git"
        assert git_caps[0].source == str(tmp_path / "git.yaml")

    def test_returns_list_of_capability_objects(self, tmp_path):
        caps = discover_capabilities(capabilities_dir=tmp_path, mcp_search_paths=[tmp_path])
        assert isinstance(caps, list)
        assert all(isinstance(c, Capability) for c in caps)
