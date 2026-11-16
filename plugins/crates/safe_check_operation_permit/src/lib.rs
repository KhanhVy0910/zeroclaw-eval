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
            "pkg-safety-check-operation-permit".to_string()
        }

        fn plugin_version() -> String {
            "0.1.0".to_string()
        }
    }

    impl Tool for Plugin {
        fn name() -> String {
            "safety.check_operation_permit".to_string()
        }

        fn description() -> String {
            "Advisory safety consultation check (R0 read-only). Verifies E-Stop, interlocks, vibration, and machine health against config/safety_rules.yaml. Returns allowed: false with reason 'SAFETY_STATE_UNKNOWN' if N4 is disconnected or safety data exceeds max_age. NOTE: Returns advisory guidance ONLY; does NOT grant an execution pass token. Gateway re-evaluates safety at command execution time!".to_string()
        }

        fn parameters_schema() -> String {
            r#"{
  "type": "object",
  "properties": {},
  "required": []
}"#.to_string()
        }

        
        fn execute(_args: String) -> Result<ToolResult, String> {
            let url = "http://127.0.0.1:8000/api/v1/n4/safety/permit";
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
