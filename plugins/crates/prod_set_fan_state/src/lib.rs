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
        fan_id: Option<i64>,
        #[serde(default)]
        state: Option<bool>,
        #[serde(default)]
        speed: Option<i64>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-production-set-fan-state".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "production.set_fan_state".to_string()
        }

        fn description() -> String {
            "Control cooling fan state and target speed (referenced in config/safety_rules.yaml: actuators). Allowed during Emergency Stop and when N4 is disconnected for emergency thermal protection.".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "fan_id": {
      "type": "integer",
      "enum": [
        1,
        2
      ],
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
  "required": [
    "state"
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
        
    }

    export!(Plugin);
}
