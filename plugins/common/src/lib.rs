pub struct HttpResponse {
    pub success: bool,
    pub body: String,
    pub error: Option<String>,
}

pub fn url_encode(s: &str) -> String {
    let mut encoded = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b == b'-' || b == b'_' || b == b'.' || b == b'~' {
            encoded.push(b as char);
        } else {
            encoded.push_str(&format!("%{:02X}", b));
        }
    }
    encoded
}

pub fn http_get(url: &str) -> HttpResponse {
    match waki::Client::new().get(url).send() {
        Ok(resp) => {
            let status_code = resp.status_code();
            let body_str = match resp.body() {
                Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                Err(e) => format!("{{\"error\": \"Failed reading response body: {e}\"}}"),
            };
            if status_code == 200 {
                HttpResponse {
                    success: true,
                    body: body_str,
                    error: None,
                }
            } else {
                HttpResponse {
                    success: false,
                    body: body_str,
                    error: Some(format!("HTTP error status {}", status_code)),
                }
            }
        }
        Err(err) => HttpResponse {
            success: false,
            body: "".to_string(),
            error: Some(format!("Failed to connect to gateway: {err}")),
        },
    }
}

pub fn http_post_json(url: &str, body: &str) -> HttpResponse {
    match waki::Client::new()
        .post(url)
        .headers([("content-type", "application/json")])
        .body(body.as_bytes().to_vec())
        .send()
    {
        Ok(resp) => {
            let status_code = resp.status_code();
            let body_str = match resp.body() {
                Ok(bytes) => String::from_utf8_lossy(&bytes).to_string(),
                Err(e) => format!("{{\"error\": \"Failed reading response body: {e}\"}}"),
            };
            if status_code == 200 {
                HttpResponse {
                    success: true,
                    body: body_str,
                    error: None,
                }
            } else {
                HttpResponse {
                    success: false,
                    body: body_str,
                    error: Some(format!("HTTP error status {}", status_code)),
                }
            }
        }
        Err(err) => HttpResponse {
            success: false,
            body: "".to_string(),
            error: Some(format!("Failed to connect to gateway: {err}")),
        },
    }
}
