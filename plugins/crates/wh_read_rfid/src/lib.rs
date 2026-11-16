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
        reader_id: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-warehouse-read-rfid".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "warehouse.read_rfid".to_string()
        }

        fn description() -> String {
            "Scan raw material RFID card reader ('gate_reader', 'dock_reader'). Returns card_id ONLY; does NOT determine batch validity or expiry.".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "reader_id": {
      "type": "string",
      "enum": [
        "gate_reader",
        "dock_reader"
      ],
      "default": "gate_reader",
      "description": "Physical RFID antenna reader identifier"
    }
  },
  "required": []
}"#.to_string()
        }

        
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
        
    }

    export!(Plugin);
}
