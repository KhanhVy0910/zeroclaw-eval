#[cfg(target_family = "wasm")]
mod component {
    wit_bindgen::generate!({
        path: "../../wit/v0",
        world: "tool-plugin",
        features: ["plugins-wit-v0"],
    });

    use exports::zeroclaw::plugin::plugin_info::Guest as PluginInfo;
    use exports::zeroclaw::plugin::tool::{Guest as Tool, ToolResult};
    #[allow(unused_imports)]
    use serde::Deserialize;
    #[allow(unused_imports)]
    use serde_json::json;

    
    #[derive(Deserialize, Default)]
    struct InputArgs {
        #[serde(default)]
        line_state: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-production-set-line-state".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "production.set_line_state".to_string()
        }

        fn description() -> String {
            "Command production line state. Parameter-based permission: 'start' is R3 and strictly verified by Gateway at runtime (blocked on E-Stop, interlock open, critical vibration, or N4 disconnect/stale data). 'hold' and 'stop' are R2 fail-safe operations and are ALWAYS accepted.".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "line_state": {
      "type": "string",
      "enum": [
        "start",
        "hold",
        "stop"
      ],
      "description": "Target state: 'start' (run - R3), 'hold' (pause - R2), or 'stop' (safe halt - R2)"
    }
  },
  "required": [
    "line_state"
  ]
}"#.to_string()
        }

        
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
        
    }

    export!(Plugin);
}
