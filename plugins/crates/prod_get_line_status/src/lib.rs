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

    

    struct Plugin;

    impl PluginInfo for Plugin {
        fn plugin_name() -> String {
            "pkg-production-get-line-status".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "production.get_line_status".to_string()
        }

        fn description() -> String {
            "Read the current operational status of the production line (run, hold, stop, fault), operating speed, and active batch/lot ID.".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {},
  "required": []
}"#.to_string()
        }

        
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n1/production/line_status";
            let res = plugin_common::http_get(url);
            Ok(ToolResult {
                success: res.success,
                output: res.body,
                error: res.error,
            })
        }
        
    }

    export!(Plugin);
}
