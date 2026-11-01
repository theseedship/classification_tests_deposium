// Vocabulary-only Uzu decision preparation: renders and tokenizes System One requests
// with the pinned hanashi::decision::DecisionEncoding, without loading weights.
// Built by scripts/build-uzu-preparation.py against a clean Uzu checkout; no runtime install.
//
// stdin:  JSONL {"case_id": str, "native_request_json": exact request body string}
// stdout: JSONL {"case_id": str, "status": "prepared"|"error", "token_ids": [u32] | null, "error": str | null}
// The request parsing mirrors the pinned CLI's DecisionRequest (choice questions only,
// option order preserved); token IDs come from the same encoder the server calls.
use std::{io::BufRead, sync::Arc};

use hanashi::DecisionEncoding;
use indexmap::IndexMap;
use serde::Deserialize;
use shoji::types::session::{
    classification::{ChatTokenCodecConfig, TokenCodecConfig},
    decision::{DecisionOption, DecisionQuestion},
};
use tokenizers::Tokenizer;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    #[serde(default)]
    #[allow(dead_code)]
    model: Option<String>,
    #[serde(default)]
    state: Option<String>,
    questions: IndexMap<String, serde_json::Value>,
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
enum Question {
    Choice {
        instructions: Option<String>,
        criteria: IndexMap<String, Option<String>>,
    },
}

#[derive(Deserialize)]
struct ChatCodec {
    prompt_template: String,
    output_parser_regex: Option<String>,
    system_role_name: String,
    user_role_name: String,
    assistant_role_name: String,
    eos_token: Option<String>,
    bos_token: Option<String>,
    end_of_thinking_tag: Option<String>,
    default_system_prompt: Option<String>,
}

fn encoding(pack: &str) -> Result<DecisionEncoding, String> {
    let config: serde_json::Value = serde_json::from_slice(
        &std::fs::read(format!("{pack}/config.json")).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    let codec = config.get("token_codec_config").ok_or("missing token_codec_config")?;
    if codec.get("type").and_then(|t| t.as_str()) != Some("ChatCodecConfig") {
        return Err("unsupported token codec".into());
    }
    let chat: ChatCodec = serde_json::from_value(codec.clone()).map_err(|e| e.to_string())?;
    // Same field mapping as uzu-engine's From<&AnyTokenCodecConfig> for the shoji type.
    let shoji = TokenCodecConfig::Chat(ChatTokenCodecConfig {
        prompt_template: chat.prompt_template,
        output_parser_regex: chat.output_parser_regex,
        system_role_name: chat.system_role_name,
        user_role_name: chat.user_role_name,
        assistant_role_name: chat.assistant_role_name,
        eos_token: chat.eos_token,
        bos_token: chat.bos_token,
        end_of_thinking_tag: chat.end_of_thinking_tag,
        default_system_prompt: chat.default_system_prompt,
    });
    let tokenizer = Tokenizer::from_bytes(std::fs::read(format!("{pack}/tokenizer.json")).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    DecisionEncoding::new(shoji, Arc::new(tokenizer)).map_err(|e| e.to_string())
}

fn prepare(encoding: &DecisionEncoding, body: &str) -> Result<Vec<u32>, String> {
    let request: Request = serde_json::from_str(body).map_err(|e| e.to_string())?;
    if request.questions.len() != 1 {
        return Err("exactly one question is supported".into());
    }
    let (_, value) = request.questions.into_iter().next().unwrap();
    let Question::Choice { instructions, criteria } = serde_json::from_value(value).map_err(|e| e.to_string())?;
    let question = DecisionQuestion::Choice {
        instructions,
        options: criteria.into_iter().map(|(key, description)| DecisionOption { key, description }).collect(),
    };
    encoding.encode(&request.state.unwrap_or_default(), &question).map_err(|e| e.to_string())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--help" {
        println!("uzu-preparation --pack PACK_DIR < requests.jsonl > prepared.jsonl (no weights, no forward)");
        return;
    }
    if args.len() != 3 || args[1] != "--pack" {
        eprintln!("invalid_arguments; use --help");
        std::process::exit(2);
    }
    let encoding = match encoding(&args[2]) {
        Ok(encoding) => encoding,
        Err(error) => {
            eprintln!("pack_codec_or_tokenizer_invalid: {error}");
            std::process::exit(2);
        },
    };
    let mut failed = false;
    for line in std::io::stdin().lock().lines() {
        let line = line.expect("stdin");
        let input: serde_json::Value = serde_json::from_str(&line).expect("jsonl");
        let case_id = input["case_id"].as_str().unwrap_or_default().to_string();
        let body = input["native_request_json"].as_str().unwrap_or_default();
        let output = match prepare(&encoding, body) {
            Ok(tokens) => serde_json::json!({"case_id": case_id, "status": "prepared", "token_ids": tokens, "error": null}),
            Err(error) => {
                failed = true;
                serde_json::json!({"case_id": case_id, "status": "error", "token_ids": null, "error": error})
            },
        };
        println!("{output}");
    }
    std::process::exit(if failed { 2 } else { 0 });
}
