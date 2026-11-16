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
        lot_id: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-warehouse-get-lot-info".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "warehouse.get_lot_info".to_string()
        }

        fn description() -> String {
            "Query warehouse material database for lot details, expiration date, and inspection status ('approved', 'quarantined', 'unknown').".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "lot_id": {
      "type": "string",
      "description": "Material batch/lot tracking code (e.g. 'LOT-2026-N1-001')"
    }
  },
  "required": [
    "lot_id"
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
        
    }

    export!(Plugin);
}
