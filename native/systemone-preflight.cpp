// Native text-only D3 preparation, using the pinned server implementation.
// This helper creates no llama_context, submits no server task and calls no decode.
// Build explicitly with scripts/build-systemone-preflight.py; no runtime install.
#include "server-decision.h"
#include "vendor/hash/hash.h"

#include <cstdlib>
#include <iostream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>

static constexpr const char * PIN = "efe3626b119ff81033e309c3ba07a770bef2c546";
static constexpr size_t MAX_BODY_BYTES = 131072;
static constexpr size_t MAX_LINE_BYTES = 1024 * 1024;

static void require(bool value) {
    if (!value) {
        throw std::runtime_error("invalid_preflight_input");
    }
}

static bool exact_keys(const json & value, const std::set<std::string> & wanted) {
    if (!value.is_object() || value.size() != wanted.size()) {
        return false;
    }
    for (const auto & key : wanted) {
        if (!value.contains(key)) {
            return false;
        }
    }
    return true;
}

static bool nonempty_text(const json & value) {
    return value.is_string() && !value.get<std::string>().empty();
}

static void usage() {
    std::cout << "systemone-preflight --model EXISTING_GGUF --model-id ALIAS --max-tokens 4096\n"
              << "stdin: JSONL {case_id, native_request_json: exact gateway request body string}\n"
              << "stdout: JSONL native preparation evidence; no weights or forward are executed\n"
              << "token_ids_sha256 hashes a compact UTF-8 JSON integer array without a newline\n"
              << "Only text-only, single choice questions with c0..c3 are supported.\n";
}

int main(int argc, char ** argv) {
    std::string model_path;
    std::string model_id;
    int max_tokens = 4096;
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            usage();
            return 0;
        }
        for (int i = 1; i < argc; ++i) {
            const std::string key = argv[i];
            require(i + 1 < argc);
            const std::string value = argv[++i];
            if (key == "--model") {
                require(model_path.empty());
                model_path = value;
            } else if (key == "--model-id") {
                require(model_id.empty());
                model_id = value;
            } else if (key == "--max-tokens") {
                size_t consumed = 0;
                max_tokens = std::stoi(value, &consumed);
                require(consumed == value.size() && max_tokens >= 128 && max_tokens <= 32768);
            } else {
                require(false);
            }
        }
        require(!model_path.empty() && !model_id.empty());
    } catch (const std::exception &) {
        std::cerr << "invalid_preflight_arguments; use --help\n";
        return 2;
    }

    // vocab_only returns before load_tensors in the pinned llama.cpp loader.
    // The metadata retains the model's actual 'systemone' Jinja template.
    llama_model_params params = llama_model_default_params();
    params.vocab_only = true;
    params.n_gpu_layers = 0;
    using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
    model_ptr model(llama_model_load_from_file(model_path.c_str(), params), llama_model_free);
    if (!model) {
        std::cerr << "native_vocabulary_load_failed\n";
        return 2;
    }
    server_decision_context decision;
    try {
        decision.init(model.get());
        require(decision.type == COMMON_DECISION_TYPE_VLLM_D3);
        require(!decision.is_joint() && !decision.can_share_prompt());
    } catch (const std::exception &) {
        std::cerr << "native_d3_metadata_invalid\n";
        return 2;
    }

    std::set<std::string> seen;
    std::string line;
    bool failed = false;
    size_t records = 0;
    while (std::getline(std::cin, line)) {
        ++records;
        json result = {
            {"schema_version", "deposium.native-systemone-encoding/v1"},
            {"source_revision", PIN},
            {"case_id", nullptr},
            {"status", "error"},
            {"max_tokens", max_tokens},
            {"vocab_only", true},
            {"weights_loaded", false},
            {"inference_context_created", false},
            {"forward_executed", false},
            {"audit_scope", "native_preparation_not_live_forward_comparison"},
        };
        try {
            require(!line.empty() && line.size() <= MAX_LINE_BYTES);
            const json input = json::parse(line);
            require(exact_keys(input, {"case_id", "native_request_json"}));
            require(nonempty_text(input["case_id"]) && nonempty_text(input["native_request_json"]));
            const std::string id = input["case_id"];
            require(id.size() <= 200 && seen.insert(id).second);
            result["case_id"] = id;
            const std::string body_bytes = input["native_request_json"];
            result["request_body_sha256"] = hash_sha256_hex(body_bytes.data(), body_bytes.size());
            result["request_body_bytes"] = body_bytes.size();
            require(body_bytes.size() <= MAX_BODY_BYTES);
            const json body = json::parse(body_bytes);
            require(exact_keys(body, {"model", "state", "questions"}));
            require(body["model"] == model_id && body["state"].is_string());
            require(exact_keys(body["questions"], {"answer"}));
            const auto & question = body["questions"]["answer"];
            require(exact_keys(question, {"type", "instructions", "criteria"}));
            require(question["type"] == "choice" && nonempty_text(question["instructions"]));
            require(exact_keys(question["criteria"], {"c0", "c1", "c2", "c3"}));
            for (const auto & item : question["criteria"].items()) {
                require(nonempty_text(item.value()));
            }

            // Call the same public C++ preparation functions as post_systemone.
            // Do not reproduce its Jinja template, label logic or tokenization.
            const auto questions = decision.parse_questions(body);
            std::vector<raw_buffer> files;
            const json state = decision.parse_state(body, files);
            require(files.empty() && questions.size() == 1);
            require(decision.n_variants(questions.front()) == 1);
            server_task task(SERVER_TASK_TYPE_DECISION);
            const mtmd_helper_init_opt init_opt = {};
            decision.fill_task(state, questions, questions.front(), 0, files, nullptr, init_opt, task);
            require(!task.tokens.has_mtmd && task.n_tokens() > 0);
            const auto & tokens = task.tokens.get_tokens();
            const std::string token_json = json(tokens).dump();
            json option_keys = json::array();
            for (const auto & option : questions.front().options) {
                option_keys.push_back(option.key);
            }
            require(option_keys == json::array({"c0", "c1", "c2", "c3"}));
            require(task.decision.labels.size() == 4);
            const bool within_limit = task.n_tokens() <= max_tokens;
            result["status"] = within_limit ? "within_limit" : "unsupported";
            result["native_input_prepared"] = true;
            result["variant_count"] = 1;
            result["variants"] = json::array({{
                {"index", 0}, {"token_count", task.n_tokens()}, {"token_ids", tokens},
                {"token_ids_sha256", hash_sha256_hex(token_json.data(), token_json.size())},
                {"token_ids_hash_encoding", "compact_utf8_json_integer_array_no_newline"},
                {"within_limit", within_limit}, {"option_keys", option_keys},
                {"label_tokens", task.decision.labels},
            }});
            if (!within_limit) {
                result["error"] = "native_prepared_sequence_exceeds_limit";
                failed = true;
            }
        } catch (const std::exception &) {
            result["error"] = "native_request_or_preparation_invalid";
            failed = true;
        }
        std::cout << result.dump() << '\n';
    }
    if (!std::cin.eof() || records == 0) {
        std::cerr << "missing_or_unreadable_preflight_records\n";
        return 2;
    }
    return failed ? 2 : 0;
}
