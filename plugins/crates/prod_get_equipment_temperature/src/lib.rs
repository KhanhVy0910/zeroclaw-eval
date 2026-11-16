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
        equipment_id: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-production-get-equipment-temperature".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "production.get_equipment_temperature".to_string()
        }

        fn description() -> String {
            "Read surface and internal temperatures for station equipment ('motor', 'control_cabinet').".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "equipment_id": {
      "type": "string",
      "enum": [
        "motor",
        "control_cabinet"
      ],
      "description": "Specific equipment component identifier"
    }
  },
  "required": []
}"#.to_string()
        }

        
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
        
    }

    export!(Plugin);
}
