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
        zone_id: Option<String>,
    }
        

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-environment-get-humidity".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "environment.get_humidity".to_string()
        }

        fn description() -> String {
            "Read ambient environmental relative humidity by zone ('hall', 'storage', 'production_floor').".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {
    "zone_id": {
      "type": "string",
      "enum": [
        "hall",
        "storage",
        "production_floor"
      ],
      "description": "Factory facility zone identifier"
    }
  },
  "required": []
}"#.to_string()
        }

        
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
        
    }

    export!(Plugin);
}
