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
        node_id: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-gateway-get-node-status".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "gateway.get_node_status".to_string()
        }

        fn description() -> String {
            "Get general communication connectivity and aggregated health status for a specific node.".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "node_id": {
      "type": "string",
      "enum": [
        "n1",
        "n2",
        "n3",
        "n4"
      ],
      "description": "Target node identifier"
    }
  },
  "required": [
    "node_id"
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
        
    }

    export!(Plugin);
}
