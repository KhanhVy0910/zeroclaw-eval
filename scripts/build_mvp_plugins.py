import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path("E:/gateway/zeroclaw-eval")
PLUGINS_DIR = BASE_DIR / "plugins"
CRATES_DIR = PLUGINS_DIR / "crates"
COMMON_DIR = PLUGINS_DIR / "common"
DIST_DIR = PLUGINS_DIR / "dist"

TOOLS = [
    {
        "tool_name": "production.get_line_status",
        "crate_name": "prod_get_line_status",
        "package_name": "pkg-production-get-line-status",
        "description": "Read the current operational status of the production line (run, hold, stop, fault), operating speed, and active batch/lot ID.",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n1/production/line_status";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "production.get_fan_status",
        "crate_name": "prod_get_fan_status",
        "package_name": "pkg-production-get-fan-status",
        "description": "Read the operational state, speed percentage, and RPM of cooling fans (fan_id 1 or 2).",
        "schema": {
            "type": "object",
            "properties": {
                "fan_id": {
                    "type": "integer",
                    "enum": [1, 2],
                    "description": "Specific fan ID to query (omit to query all fans)"
                }
            },
            "required": []
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        fan_id: Option<i64>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = serde_json::from_str(&args).unwrap_or_default();
            let url = match input.fan_id {
                Some(id) => format!("http://127.0.0.1:8000/api/v1/n1/production/fan_status?fan_id={id}"),
                None => "http://127.0.0.1:8000/api/v1/n1/production/fan_status".to_string(),
            };
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "production.get_equipment_temperature",
        "crate_name": "prod_get_equipment_temperature",
        "package_name": "pkg-production-get-equipment-temperature",
        "description": "Read surface and internal temperatures for station equipment ('motor', 'control_cabinet').",
        "schema": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "enum": ["motor", "control_cabinet"],
                    "description": "Specific equipment component identifier"
                }
            },
            "required": []
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        equipment_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = serde_json::from_str(&args).unwrap_or_default();
            let url = match input.equipment_id.as_deref() {
                Some(id) => format!("http://127.0.0.1:8000/api/v1/n1/production/equipment_temperature?equipment_id={}", plugin_common::url_encode(id)),
                None => "http://127.0.0.1:8000/api/v1/n1/production/equipment_temperature".to_string(),
            };
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "production.set_fan_state",
        "crate_name": "prod_set_fan_state",
        "package_name": "pkg-production-set-fan-state",
        "description": "Control cooling fan state and target speed (referenced in config/safety_rules.yaml: actuators). Allowed during Emergency Stop and when N4 is disconnected for emergency thermal protection.",
        "schema": {
            "type": "object",
            "properties": {
                "fan_id": {
                    "type": "integer",
                    "enum": [1, 2],
                    "default": 1,
                    "description": "Target fan identifier"
                },
                "state": {
                    "type": "boolean",
                    "description": "true = enable fan, false = disable fan"
                },
                "speed": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Optional PWM speed percentage (defaults to 100 when enabled)"
                }
            },
            "required": ["state"]
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        fan_id: Option<i64>,
        #[serde(default)]
        state: Option<bool>,
        #[serde(default)]
        speed: Option<i64>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = match serde_json::from_str(&args) {
                Ok(v) => v,
                Err(e) => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Invalid arguments: {e}")),
                    });
                }
            };
            let state = match input.state {
                Some(s) => s,
                None => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some("Missing required argument: 'state'".to_string()),
                    });
                }
            };
            let fan_id = input.fan_id.unwrap_or(1);
            let speed = input.speed.unwrap_or(if state { 100 } else { 0 });
            let req_body = json!({
                "fan_id": fan_id,
                "state": state,
                "speed": speed,
            }).to_string();
            let url = "http://127.0.0.1:8000/api/v1/n1/production/fan";
            let res = plugin_common::http_post_json(url, &req_body);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "production.set_line_state",
        "crate_name": "prod_set_line_state",
        "package_name": "pkg-production-set-line-state",
        "description": "Command production line state. Parameter-based permission: 'start' is R3 and strictly verified by Gateway at runtime (blocked on E-Stop, interlock open, critical vibration, or N4 disconnect/stale data). 'hold' and 'stop' are R2 fail-safe operations and are ALWAYS accepted.",
        "schema": {
            "type": "object",
            "properties": {
                "line_state": {
                    "type": "string",
                    "enum": ["start", "hold", "stop"],
                    "description": "Target state: 'start' (run - R3), 'hold' (pause - R2), or 'stop' (safe halt - R2)"
                }
            },
            "required": ["line_state"]
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        line_state: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = match serde_json::from_str(&args) {
                Ok(v) => v,
                Err(e) => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Invalid arguments: {e}")),
                    });
                }
            };
            let line_state = match input.line_state {
                Some(s) => s,
                None => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some("Missing required argument: 'line_state'".to_string()),
                    });
                }
            };
            let req_body = json!({
                "line_state": line_state,
            }).to_string();
            let url = "http://127.0.0.1:8000/api/v1/n1/production/line_state";
            let res = plugin_common::http_post_json(url, &req_body);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "environment.get_temperature",
        "crate_name": "env_get_temperature",
        "package_name": "pkg-environment-get-temperature",
        "description": "Read ambient environmental temperature by zone ('hall', 'storage', 'production_floor').",
        "schema": {
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "enum": ["hall", "storage", "production_floor"],
                    "description": "Factory facility zone identifier"
                }
            },
            "required": []
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        zone_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = serde_json::from_str(&args).unwrap_or_default();
            let url = match input.zone_id.as_deref() {
                Some(zid) => format!("http://127.0.0.1:8000/api/v1/n2/environment/temperature?zone_id={}", plugin_common::url_encode(zid)),
                None => "http://127.0.0.1:8000/api/v1/n2/environment/temperature".to_string(),
            };
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "environment.get_humidity",
        "crate_name": "env_get_humidity",
        "package_name": "pkg-environment-get-humidity",
        "description": "Read ambient environmental relative humidity by zone ('hall', 'storage', 'production_floor').",
        "schema": {
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "enum": ["hall", "storage", "production_floor"],
                    "description": "Factory facility zone identifier"
                }
            },
            "required": []
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        zone_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = serde_json::from_str(&args).unwrap_or_default();
            let url = match input.zone_id.as_deref() {
                Some(zid) => format!("http://127.0.0.1:8000/api/v1/n2/environment/humidity?zone_id={}", plugin_common::url_encode(zid)),
                None => "http://127.0.0.1:8000/api/v1/n2/environment/humidity".to_string(),
            };
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "warehouse.read_rfid",
        "crate_name": "wh_read_rfid",
        "package_name": "pkg-warehouse-read-rfid",
        "description": "Scan raw material RFID card reader ('gate_reader', 'dock_reader'). Returns card_id ONLY; does NOT determine batch validity or expiry.",
        "schema": {
            "type": "object",
            "properties": {
                "reader_id": {
                    "type": "string",
                    "enum": ["gate_reader", "dock_reader"],
                    "default": "gate_reader",
                    "description": "Physical RFID antenna reader identifier"
                }
            },
            "required": []
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        reader_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = serde_json::from_str(&args).unwrap_or_default();
            let rid = input.reader_id.as_deref().unwrap_or("gate_reader");
            let url = format!("http://127.0.0.1:8000/api/v1/n3/warehouse/rfid?reader_id={}", plugin_common::url_encode(rid));
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "warehouse.get_lot_info",
        "crate_name": "wh_get_lot_info",
        "package_name": "pkg-warehouse-get-lot-info",
        "description": "Query warehouse material database for lot details, expiration date, and inspection status ('approved', 'quarantined', 'unknown').",
        "schema": {
            "type": "object",
            "properties": {
                "lot_id": {
                    "type": "string",
                    "description": "Material batch/lot tracking code (e.g. 'LOT-2026-N1-001')"
                }
            },
            "required": ["lot_id"]
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        lot_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = match serde_json::from_str(&args) {
                Ok(v) => v,
                Err(e) => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Invalid arguments: {e}")),
                    });
                }
            };
            let lot_id = match input.lot_id.as_deref() {
                Some(lid) => lid,
                None => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some("Missing required argument: 'lot_id'".to_string()),
                    });
                }
            };
            let url = format!("http://127.0.0.1:8000/api/v1/n3/warehouse/lot_info?lot_id={}", plugin_common::url_encode(lot_id));
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "maintenance.get_vibration",
        "crate_name": "maint_get_vibration",
        "package_name": "pkg-maintenance-get-vibration",
        "description": "Read 3-axis (x, y, z) vibration acceleration and computed RMS vibration velocity (mm/s). Thresholds referenced in config/safety_rules.yaml: vibration.",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n4/maintenance/vibration";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "maintenance.get_machine_health",
        "crate_name": "maint_get_machine_health",
        "package_name": "pkg-maintenance-get-machine-health",
        "description": "Read computed machine operational health status ('nominal', 'warning', 'critical'), health score (0..100), and anomaly flag. Computed SOLELY from N4 telemetry (vibration, current, anomalies) per config/safety_rules.yaml; independent of N1.",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n4/maintenance/health";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "safety.get_emergency_state",
        "crate_name": "safe_get_emergency_state",
        "package_name": "pkg-safety-get-emergency-state",
        "description": "Read physical Emergency Stop safety relay contact state. Mapping: internal boolean emergency_stop (true/false) maps to output status ('ENGAGED'/'RELEASED'). Read-only: no agent tool can engage or clear E-Stop.",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n4/safety/emergency";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "safety.check_operation_permit",
        "crate_name": "safe_check_operation_permit",
        "package_name": "pkg-safety-check-operation-permit",
        "description": "Advisory safety consultation check (R0 read-only). Verifies E-Stop, interlocks, vibration, and machine health against config/safety_rules.yaml. Returns allowed: false with reason 'SAFETY_STATE_UNKNOWN' if N4 is disconnected or safety data exceeds max_age. NOTE: Returns advisory guidance ONLY; does NOT grant an execution pass token. Gateway re-evaluates safety at command execution time!",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n4/safety/permit";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "gateway.list_nodes",
        "crate_name": "gw_list_nodes",
        "package_name": "pkg-gateway-list-nodes",
        "description": "List all active industrial hardware nodes connected to the Hardware Gateway (N1, N2, N3, N4).",
        "schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "input_struct": "",
        "exec_code": """
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/gateway/nodes";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
    {
        "tool_name": "gateway.get_node_status",
        "crate_name": "gw_get_node_status",
        "package_name": "pkg-gateway-get-node-status",
        "description": "Get general communication connectivity and aggregated health status for a specific node.",
        "schema": {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "enum": ["n1", "n2", "n3", "n4"],
                    "description": "Target node identifier"
                }
            },
            "required": ["node_id"]
        },
        "input_struct": """
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        node_id: Option<String>,
    }
        """,
        "exec_code": """
        fn execute(args: String) -> Result<ToolResult, String> {
            let input: InputArgs = match serde_json::from_str(&args) {
                Ok(v) => v,
                Err(e) => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Invalid arguments: {e}")),
                    });
                }
            };
            let node_id = match input.node_id.as_deref() {
                Some(nid) => nid,
                None => {
                    return Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some("Missing required argument: 'node_id'".to_string()),
                    });
                }
            };
            let url = format!("http://127.0.0.1:8000/api/v1/{}/status", plugin_common::url_encode(node_id));
            let res = plugin_common::http_get(&url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        """
    },
]

def generate_workspace():
    print("Generating workspace files...")
    CRATES_DIR.mkdir(parents=True, exist_ok=True)
    COMMON_DIR.mkdir(parents=True, exist_ok=True)
    (COMMON_DIR / "src").mkdir(parents=True, exist_ok=True)

    # plugins/Cargo.toml
    members = ['"common"'] + ['"crates/' + t["crate_name"] + '"' for t in TOOLS]
    members_str = ",\n    ".join(members)
    workspace_cargo = f"""[workspace]
members = [
    {members_str}
]
resolver = "2"

[workspace.dependencies]
wit-bindgen = "0.46"
serde = {{ version = "1.0", features = ["derive"] }}
serde_json = "1.0"
waki = "0.5.1"
plugin-common = {{ path = "common" }}

[profile.release]
opt-level = "s"
lto = true
strip = true
"""
    (PLUGINS_DIR / "Cargo.toml").write_text(workspace_cargo, encoding="utf-8")

    # plugins/common/Cargo.toml
    common_cargo = """[package]
name = "plugin-common"
version = "0.1.0"
edition = "2024"

[dependencies]
waki.workspace = true
"""
    (COMMON_DIR / "Cargo.toml").write_text(common_cargo, encoding="utf-8")

    # plugins/common/src/lib.rs
    common_lib = """pub struct HttpResponse {
    pub success: bool,
    pub body: String,
    pub error: Option<String>,
}

pub fn url_encode(s: &str) -> String {
    let mut encoded = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b == b'-' || b == b'_' || b == b'.' || b == b'~' {
            encoded.push(b as char);
        } else {
            encoded.push_str(&format!("%{:02X}", b));
        }
    }
    encoded
}

pub fn http_get(url: &str) -> HttpResponse {
    match waki::Client::new().get(url).send() {
        Ok(resp) => {
            let status_code = resp.status_code();
            let body_str = match resp.body() {
                Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                Err(e) => format!("{{\\"error\\": \\"Failed reading response body: {e}\\"}}"),
            };
            if status_code == 200 {
                HttpResponse {
                    success: true,
                    body: body_str,
                    error: None,
                }
            } else {
                HttpResponse {
                    success: false,
                    body: body_str,
                    error: Some(format!("HTTP error status {}", status_code)),
                }
            }
        }
        Err(err) => HttpResponse {
            success: false,
            body: "".to_string(),
            error: Some(format!("Failed to connect to gateway: {err}")),
        },
    }
}

pub fn http_post_json(url: &str, body: &str) -> HttpResponse {
    match waki::Client::new()
        .post(url)
        .headers([("content-type", "application/json")])
        .body(body.as_bytes().to_vec())
        .send()
    {
        Ok(resp) => {
            let status_code = resp.status_code();
            let body_str = match resp.body() {
                Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                Err(e) => format!("{{\\"error\\": \\"Failed reading response body: {e}\\"}}"),
            };
            if status_code == 200 {
                HttpResponse {
                    success: true,
                    body: body_str,
                    error: None,
                }
            } else {
                HttpResponse {
                    success: false,
                    body: body_str,
                    error: Some(format!("HTTP error status {}", status_code)),
                }
            }
        }
        Err(err) => HttpResponse {
            success: false,
            body: "".to_string(),
            error: Some(format!("Failed to connect to gateway: {err}")),
        },
    }
}
"""
    (COMMON_DIR / "src" / "lib.rs").write_text(common_lib, encoding="utf-8")

    # Generate each tool crate
    for t in TOOLS:
        crate_dir = CRATES_DIR / t["crate_name"]
        (crate_dir / "src").mkdir(parents=True, exist_ok=True)

        crate_cargo = f"""[package]
name = "{t['crate_name']}"
version = "0.1.0"
edition = "2024"

[lib]
crate-type = ["cdylib"]

[dependencies]
wit-bindgen.workspace = true
serde.workspace = true
serde_json.workspace = true
plugin-common.workspace = true
"""
        (crate_dir / "Cargo.toml").write_text(crate_cargo, encoding="utf-8")

        schema_escaped = json.dumps(t["schema"], indent=2)
        desc_escaped = t["description"].replace('"', '\\"')

        crate_lib = f"""#[cfg(target_family = "wasm")]
mod component {{
    wit_bindgen::generate!({{
        path: "../../wit/v0",
        world: "tool-plugin",
        features: ["plugins-wit-v0"],
    }});

    use exports::zeroclaw::plugin::plugin_info::Guest as PluginInfo;
    use exports::zeroclaw::plugin::tool::{{Guest as Tool, ToolResult}};
    #[allow(unused_imports)]
    use serde::Deserialize;
    #[allow(unused_imports)]
    use serde_json::json;

    {t['input_struct']}

    struct Plugin;

    impl PluginInfo for Plugin {{
        fn plugin_name() -> String {{
            "{t['package_name']}".to_string()
        }}

        fn plugin_version() -> String {{
            "0.1.0".to_string()
        }}
    }}

    impl Tool for Plugin {{
        fn name() -> String {{
            "{t['tool_name']}".to_string()
        }}

        fn description() -> String {{
            "{desc_escaped}".to_string()
        }}

        fn parameters_schema() -> String {{
            r#"{schema_escaped}"#.to_string()
        }}

        {t['exec_code']}
    }}

    export!(Plugin);
}}
"""
        (crate_dir / "src" / "lib.rs").write_text(crate_lib, encoding="utf-8")
    print(f"Generated {len(TOOLS)} tool crates successfully.")


def build_wasm():
    print("Building WASM components with cargo...")
    cmd = ["cargo", "build", "--target", "wasm32-wasip2", "--release"]
    res = subprocess.run(cmd, cwd=str(PLUGINS_DIR), capture_output=True, text=True)
    if res.returncode != 0:
        print("Build FAILED!")
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        sys.exit(1)
    print("Build SUCCEEDED!")


def populate_dist():
    print("Populating plugins/dist...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target_release = PLUGINS_DIR / "target" / "wasm32-wasip2" / "release"

    for t in TOOLS:
        pkg_dir = DIST_DIR / t["package_name"]
        pkg_dir.mkdir(parents=True, exist_ok=True)

        wasm_src = target_release / f"{t['crate_name']}.wasm"
        wasm_dest_name = f"{t['package_name'].replace('-', '_')}.wasm"
        wasm_dest = pkg_dir / wasm_dest_name

        if not wasm_src.exists():
            print(f"ERROR: Compiled wasm not found: {wasm_src}")
            sys.exit(1)

        shutil.copyfile(wasm_src, wasm_dest)
        size_kb = wasm_dest.stat().st_size / 1024
        print(f"  {t['package_name']}: copied {wasm_dest_name} ({size_kb:.1f} KB)")

        desc_escaped = t["description"].replace('"', '\\"')
        manifest = f"""name = "{t['package_name']}"
version = "0.1.0"
description = "{desc_escaped}"
author = "ZeroClaw Evaluation Team"
wasm_path = "{wasm_dest_name}"
capabilities = ["tool"]
permissions = ["http_client"]

[egress]
hosts = ["127.0.0.1"]
"""
        (pkg_dir / "manifest.toml").write_text(manifest, encoding="utf-8")


def generate_config_snippet():
    print("\nGenerating config/config.toml plugin entries...")
    entries = []
    for t in TOOLS:
        pkg_name = t["package_name"]
        val = json.dumps([pkg_name, "tool", pkg_name], separators=(',', ':')).encode('utf-8')
        instance_key = "zpi1_" + base64.urlsafe_b64encode(val).decode('utf-8').rstrip('=')
        entries.append(f"""[[plugins.entries]]
name = "{instance_key}"
egress_hosts = ["127.0.0.1"]
egress_allow_private = ["127.0.0.1"]

[[plugins.entries]]
name = "{pkg_name}"
egress_hosts = ["127.0.0.1"]
egress_allow_private = ["127.0.0.1"]""")

    snippet = "\n\n".join(entries)
    return snippet


if __name__ == "__main__":
    generate_workspace()
    build_wasm()
    populate_dist()
    snippet = generate_config_snippet()
    with open(BASE_DIR / "config" / "plugins_snippet.toml", "w", encoding="utf-8") as f:
        f.write(snippet)
    print("Done! Config snippet written to config/plugins_snippet.toml")
