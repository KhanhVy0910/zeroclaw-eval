#[cfg(target_family = "wasm")]
mod component {
    wit_bindgen::generate!({
        path: "wit/v0",
        world: "tool-plugin",
        features: ["plugins-wit-v0"],
    });

    use exports::zeroclaw::plugin::plugin_info::Guest as PluginInfo;
    use exports::zeroclaw::plugin::tool::{Guest as Tool, ToolResult};
    use serde::{Deserialize, Serialize};
    use serde_json::json;

    struct ProductionPlugin;

    #[derive(Deserialize, Default)]
    struct ToolInputArgs {
        #[serde(default)]
        action: Option<String>,
        #[serde(default)]
        state: Option<serde_json::Value>,
    }

    impl PluginInfo for ProductionPlugin {
        fn plugin_name() -> String {
            "production".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for ProductionPlugin {
        fn name() -> String {
            "production".to_string()
        }

        fn description() -> String {
            "Production Control Tool for Node N1 (ESP32 DevKit). Actions: 'get_status' (or 'production.get_status') to inspect line state and cooling fan; 'set_fan' (or 'production.set_fan') with parameter 'state' (boolean or integer) to control cooling fan."
                .to_string()
        }

        fn parameters_schema() -> String {
            json!({
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get_status", "set_fan", "production.get_status", "production.set_fan"],
                        "description": "Action to perform: 'get_status' to query sensor/machine status, 'set_fan' to turn the cooling fan ON or OFF."
                    },
                    "state": {
                        "type": "boolean",
                        "description": "Target fan state for set_fan: true for ON, false for OFF."
                    }
                },
                "required": ["action"]
            })
            .to_string()
        }

        fn execute(args: String) -> Result<ToolResult, String> {
            let input: ToolInputArgs = serde_json::from_str(&args).unwrap_or_default();
            let action = input.action.as_deref().unwrap_or("get_status");

            if action == "get_status" || action == "production.get_status" {
                let url = "http://127.0.0.1:8000/api/v1/n1/production/status";
                match waki::Client::new().get(url).send() {
                    Ok(resp) => {
                        let status_code = resp.status_code();
                        let body_str = match resp.body() {
                            Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                            Err(e) => format!("{{\"error\": \"Failed reading response body: {e}\"}}"),
                        };
                        if status_code == 200 {
                            Ok(ToolResult {
                                success: true,
                                output: body_str,
                                error: None,
                            })
                        } else {
                            Ok(ToolResult {
                                success: false,
                                output: body_str,
                                error: Some(format!("HTTP error status {}", status_code)),
                            })
                        }
                    }
                    Err(err) => Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Failed to connect to gateway: {err}")),
                    }),
                }
            } else if action == "set_fan" || action == "production.set_fan" {
                let url = "http://127.0.0.1:8000/api/v1/n1/production/fan";
                let target_state = input.state.unwrap_or(serde_json::Value::Bool(true));
                let req_body = json!({ "state": target_state }).to_string();

                match waki::Client::new()
                    .post(url)
                    .headers([("content-type", "application/json")])
                    .body(req_body.into_bytes())
                    .send()
                {
                    Ok(resp) => {
                        let status_code = resp.status_code();
                        let body_str = match resp.body() {
                            Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                            Err(e) => format!("{{\"error\": \"Failed reading response body: {e}\"}}"),
                        };
                        if status_code == 200 {
                            Ok(ToolResult {
                                success: true,
                                output: body_str,
                                error: None,
                            })
                        } else {
                            Ok(ToolResult {
                                success: false,
                                output: body_str,
                                error: Some(format!("HTTP error status {}", status_code)),
                            })
                        }
                    }
                    Err(err) => Ok(ToolResult {
                        success: false,
                        output: "".to_string(),
                        error: Some(format!("Failed to connect to gateway: {err}")),
                    }),
                }
            } else {
                Ok(ToolResult {
                    success: false,
                    output: "".to_string(),
                    error: Some(format!("Unsupported action '{action}'")),
                })
            }
        }
    }

    export!(ProductionPlugin);
}
