"""Unit tests for Task T5c: 15 MVP WASM Plugin Packages (Option A)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import tomllib
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIST = REPO_ROOT / "plugins" / "dist"
CONFIG_FILE = REPO_ROOT / "config" / "config.toml"
TOOLS_YAML = REPO_ROOT / "tools.yaml"
CARGO_TOML = REPO_ROOT / "plugins" / "Cargo.toml"

EXPECTED_MVP_TOOLS = [
    "production.get_line_status",
    "production.get_fan_status",
    "production.get_equipment_temperature",
    "production.set_fan_state",
    "production.set_line_state",
    "environment.get_temperature",
    "environment.get_humidity",
    "warehouse.read_rfid",
    "warehouse.get_lot_info",
    "maintenance.get_vibration",
    "maintenance.get_machine_health",
    "safety.get_emergency_state",
    "safety.check_operation_permit",
    "gateway.list_nodes",
    "gateway.get_node_status",
]


def _tool_to_pkg_name(tool_name: str) -> str:
    return f"pkg-{tool_name.replace('.', '-').replace('_', '-')}"


def test_all_15_plugins_exist_in_dist():
    """Verify that all 15 MVP plugin packages exist in plugins/dist/."""
    assert PLUGINS_DIST.exists(), f"plugins/dist not found at {PLUGINS_DIST}"
    for tool_name in EXPECTED_MVP_TOOLS:
        pkg_name = _tool_to_pkg_name(tool_name)
        pkg_dir = PLUGINS_DIST / pkg_name
        assert pkg_dir.exists() and pkg_dir.is_dir(), f"Plugin directory {pkg_name} does not exist in plugins/dist"


def test_plugin_manifests_valid():
    """Verify each plugin package has a valid manifest.toml and .wasm binary."""
    for tool_name in EXPECTED_MVP_TOOLS:
        pkg_name = _tool_to_pkg_name(tool_name)
        manifest_path = PLUGINS_DIST / pkg_name / "manifest.toml"
        assert manifest_path.exists(), f"manifest.toml missing in {pkg_name}"

        with open(manifest_path, "rb") as f:
            manifest = tomllib.load(f)

        assert manifest.get("name") == pkg_name
        assert manifest.get("capabilities") == ["tool"]
        assert manifest.get("permissions") == ["http_client"]
        assert manifest.get("egress", {}).get("hosts") == ["127.0.0.1"]

        wasm_path = PLUGINS_DIST / pkg_name / manifest.get("wasm_path", "")
        assert wasm_path.exists(), f"WASM binary missing: {wasm_path}"
        assert wasm_path.stat().st_size > 50 * 1024, f"WASM binary abnormally small ({wasm_path.stat().st_size} bytes)"


def test_config_toml_has_all_plugin_entries():
    """Verify config/config.toml registers all 15 plugins with valid egress rules."""
    assert CONFIG_FILE.exists(), f"config.toml missing at {CONFIG_FILE}"
    with open(CONFIG_FILE, "rb") as f:
        cfg = tomllib.load(f)

    assert cfg.get("plugins", {}).get("enabled") is True
    assert cfg.get("plugins", {}).get("auto_discover") is True
    assert cfg.get("plugins", {}).get("max_active_instances", 0) >= 15

    entries = cfg.get("plugins", {}).get("entries", [])
    entry_names = {e.get("name") for e in entries}

    for tool_name in EXPECTED_MVP_TOOLS:
        pkg_name = _tool_to_pkg_name(tool_name)

        # 1. Package name entry check
        assert pkg_name in entry_names, f"Package entry missing in config.toml: {pkg_name}"

        # 2. Canonical instance key entry check
        val = json.dumps([pkg_name, "tool", pkg_name], separators=(',', ':')).encode('utf-8')
        instance_key = "zpi1_" + base64.urlsafe_b64encode(val).decode('utf-8').rstrip('=')
        assert instance_key in entry_names, f"Instance key entry missing in config.toml: {instance_key}"

        # 3. Verify egress policy on the entry
        for e in entries:
            if e.get("name") in (pkg_name, instance_key):
                assert e.get("egress_hosts") == ["127.0.0.1"]
                assert e.get("egress_allow_private") == ["127.0.0.1"]


def test_plugin_tool_names_match_tools_yaml():
    """Verify tools match the MVP tools declared in tools.yaml."""
    with open(TOOLS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    yaml_mvp = [t["name"] for t in data["tools"] if t.get("mvp")]

    assert sorted(yaml_mvp) == sorted(EXPECTED_MVP_TOOLS), "MVP tools in tools.yaml do not match expected 15 tools"


def test_cargo_workspace_members():
    """Verify plugins/Cargo.toml contains common and all 15 crates as workspace members."""
    assert CARGO_TOML.exists()
    with open(CARGO_TOML, "rb") as f:
        cargo_data = tomllib.load(f)

    members = cargo_data.get("workspace", {}).get("members", [])
    assert "common" in members
    for tool_name in EXPECTED_MVP_TOOLS:
        crate_name = f"crates/{tool_name.replace('production.', 'prod_').replace('environment.', 'env_').replace('warehouse.', 'wh_').replace('maintenance.', 'maint_').replace('safety.', 'safe_').replace('gateway.', 'gw_')}"
        assert crate_name in members, f"Crate {crate_name} missing from workspace members"
