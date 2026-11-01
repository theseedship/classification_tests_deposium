"""Uzu decision transport: reuse System One projection, HTTP and validation.

No model library, discovery, download or service launch occurs on import or
construction. Prediction requires the matching live owned-process supervisor.
"""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import re

from . import systemone_local as local
from .native_supervision import require_native_supervision
from .worker_transport import decode

UZU_REVISION = "d3d3a5b20a3de507522e1099457d1dae0243effb"  # release 0.6.15 (official CLI binary)
PACK_REVISION = "86f617b67e3f0ce02fe678c38801e2296a303777"
PACK_REPO = "trymirai/d3-flash-M"
REPOSITORY = "https://github.com/trymirai/uzu.git"
REQUIRED_FILES = {"model.safetensors", "config.json", "chat_template.jinja",
                  "tokenizer.json", "tokenizer_config.json", "LICENSE"}
MAX_METADATA = 1024 * 1024


def require(value, code):
    if not value:
        raise ValueError(code)


def closed(value, fields, code):
    require(isinstance(value, dict) and set(value) == set(fields), code)


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def read_metadata(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file()
            and path.stat().st_size <= MAX_METADATA, "uzu_metadata_missing_or_large")
    before = local._state(path)
    data = path.read_bytes()
    require(len(data) <= MAX_METADATA and before == local._state(path), "uzu_metadata_changed")
    return decode(data)


def validate_model_profile(profile):
    # Reuse loopback, endpoint, timeout and memory-budget checks. This proxy is
    # validation-only: no saved profile or identity is relabelled as llama.cpp.
    require(profile.get("adapter") == "uzu_systemone_local", "uzu_profile_invalid")
    model = profile.get("model")
    require(isinstance(model, dict) and model.get("credential_env") is None,
            "uzu_profile_has_no_authentication_claim")
    proxy = {**profile, "adapter": "systemone_local",
             "model": {**model, "credential_env": local.AUTH_ENV}}
    local.validate_model_profile(proxy)
    require(model["repo_id"] == PACK_REPO and profile["revision"] == PACK_REVISION,
            "uzu_unreviewed_pack")


def verify_pack(root, manifest_path, remember):
    """Check all runtime inputs; expected hashes are declarations, not signatures.

    The caller must admit memory before this explicit full-file verification.
    No missing file is fetched. Extra files (notably encoding.json) are refused.
    """
    root, manifest_path = Path(root), Path(manifest_path)
    require(not root.is_symlink() and root.is_dir(), "uzu_pack_directory_invalid")
    manifest = read_metadata(manifest_path)
    closed(manifest, {"schema_version", "repo_id", "revision", "files"}, "uzu_assets_invalid")
    require(manifest["schema_version"] == "deposium.model-assets/v1"
            and manifest["repo_id"] == PACK_REPO and manifest["revision"] == PACK_REVISION
            and isinstance(manifest["files"], list), "uzu_assets_invalid")
    names = set()
    for entry in manifest["files"]:
        closed(entry, {"path", "size", "sha256"}, "uzu_asset_entry_invalid")
        name = entry["path"]
        require(isinstance(name, str) and name in REQUIRED_FILES and name not in names
                and type(entry["size"]) is int and entry["size"] > 0 and sha(entry["sha256"]),
                "uzu_asset_entry_invalid")
        ceiling = 8 * 2**30 if name == "model.safetensors" else 64 * 2**20 if name == "tokenizer.json" else MAX_METADATA
        require(entry["size"] <= ceiling, "uzu_asset_size_limit")
        names.add(name)
    require(names == REQUIRED_FILES and {p.name for p in root.iterdir()} == REQUIRED_FILES,
            "uzu_pack_inventory_mismatch")
    remember(manifest_path, local.digest(manifest_path))
    for entry in manifest["files"]:
        path = root / entry["path"]
        require(not path.is_symlink() and path.is_file() and path.stat().st_size == entry["size"],
                "uzu_asset_size_or_type_invalid")
        remember(path, entry["sha256"])
    config = read_metadata(root / "config.json")
    require(isinstance(config, dict) and config.get("type") == "DecisionModelConfig",
            "uzu_decision_model_required")
    decision = config.get("decision")
    closed(decision, {"codes", "temperature"}, "uzu_decision_config_invalid")
    codes, temperature = decision["codes"], decision["temperature"]
    require(isinstance(codes, list) and len(codes) == 255
            and all(isinstance(code, str) and code.strip() for code in codes)
            and len(set(codes)) == len(codes)
            and type(temperature) in (int, float) and math.isfinite(temperature)
            and temperature == 1, "uzu_decision_config_invalid")
    codec = config.get("token_codec_config")
    require(isinstance(codec, dict), "uzu_template_mismatch")
    template = codec.get("prompt_template")
    require(isinstance(template, str) and template
            and template == (root / "chat_template.jinja").read_text(), "uzu_template_mismatch")
    return manifest


def preparation_map(value, *, model_id, assets_sha256, max_tokens):
    """Validate a source-bound preparation receipt, never fabricate token counts.

    The real Uzu-renderer producer is a separate native preparation prerequisite;
    CPU fixtures do not certify that producer or its receipts.
    """
    closed(value, {"schema_version", "uzu_revision", "model_id", "assets_sha256", "max_tokens",
                   "renderer", "weights_loaded", "forward_executed", "request_tokens", "overflow_control"},
           "uzu_preparation_invalid")
    require(value["schema_version"] == "deposium.uzu-input-preparation/v1"
            and value["uzu_revision"] == UZU_REVISION and value["model_id"] == model_id
            and value["assets_sha256"] == assets_sha256 and value["max_tokens"] == max_tokens
            and type(value["max_tokens"]) is int
            and value["renderer"] == "hanashi::decision::DecisionEncoding"
            and value["weights_loaded"] is False and value["forward_executed"] is False,
            "uzu_preparation_binding_invalid")
    entries = value["request_tokens"]
    require(isinstance(entries, dict) and 0 < len(entries) <= 4096, "uzu_preparation_empty_or_large")
    counts = {}
    for body_hash, row in entries.items():
        closed(row, {"input_tokens", "token_ids_sha256"}, "uzu_preparation_entry_invalid")
        require(sha(body_hash) and type(row["input_tokens"]) is int
                and 0 < row["input_tokens"] <= max_tokens and sha(row["token_ids_sha256"]),
                "uzu_preparation_entry_invalid")
        counts[body_hash] = row["input_tokens"]
    negative = value["overflow_control"]
    closed(negative, {"request_body_sha256", "input_tokens", "token_ids_sha256"},
           "uzu_overflow_control_invalid")
    require(sha(negative["request_body_sha256"]) and negative["request_body_sha256"] not in counts
            and type(negative["input_tokens"]) is int and negative["input_tokens"] > max_tokens
            and sha(negative["token_ids_sha256"]), "uzu_overflow_control_invalid")
    return counts


class UzuSystemOneAdapter(local.LocalSystemOneAdapter):
    profile_validator = staticmethod(validate_model_profile)
    adapter_name = "uzu_systemone_local"
    requires_auth = False

    def _bind_session(self, profile_path):
        self._profile_path = Path(profile_path).absolute()
        # A saved session alone may not rehash a resident pack or contact it.
        require_native_supervision(self._profile, self._profile_path)
        path = self._profile_path.parent / self._model["session_manifest"]
        self._remember(path, self._model["session_sha256"])
        session = self._session = read_metadata(path)
        closed(session, {"schema_version", "model", "runtime", "preparation", "endpoint", "settings",
                         "max_rss_mb", "pid", "supervisor"}, "uzu_session_invalid")
        model, runtime = session["model"], session["runtime"]
        closed(model, {"repo_id", "revision", "alias", "path", "assets_manifest", "assets_sha256"},
               "uzu_model_identity_invalid")
        closed(runtime, {"repository", "revision", "binary", "sha256"}, "uzu_runtime_identity_invalid")
        settings = session["settings"]
        closed(settings, {"client_max_tokens", "concurrency", "questions_per_call", "implicit_acquisition"},
               "uzu_settings_invalid")
        require(all(type(settings[key]) is int for key in
                    ("client_max_tokens", "concurrency", "questions_per_call"))
                and settings["implicit_acquisition"] is False, "uzu_settings_invalid")
        require(session["schema_version"] == "deposium.uzu-model-session/v1"
                and model["repo_id"] == self._model["repo_id"]
                and model["revision"] == self._profile["revision"]
                and model["alias"] == self._model["model_id"]
                and session["endpoint"] == self._model["endpoint"]
                and session["max_rss_mb"] == self._model["max_rss_mb"]
                and session["settings"] == {"client_max_tokens": self._model["max_length"],
                    "concurrency": 1, "questions_per_call": 1, "implicit_acquisition": False}
                and runtime["repository"] == REPOSITORY and runtime["revision"] == UZU_REVISION
                and sha(runtime["sha256"]) and sha(model["assets_sha256"]), "uzu_session_identity_mismatch")
        manifest = Path(model["assets_manifest"])
        require(all(isinstance(value, str) and Path(value).is_absolute() for value in
                    (model["path"], model["assets_manifest"], runtime["binary"])),
                "uzu_absolute_asset_paths_required")
        self._remember(manifest, model["assets_sha256"])
        verify_pack(model["path"], manifest, self._remember)
        self._remember(Path(runtime["binary"]), runtime["sha256"])
        binding = session["preparation"]
        closed(binding, {"path", "sha256"}, "uzu_preparation_binding_invalid")
        require(sha(binding["sha256"]) and isinstance(binding["path"], str)
                and Path(binding["path"]).is_absolute(), "uzu_preparation_binding_invalid")
        self._remember(Path(binding["path"]), binding["sha256"])
        self._prepared_tokens = preparation_map(read_metadata(binding["path"]),
            model_id=model["alias"], assets_sha256=model["assets_sha256"], max_tokens=self._model["max_length"])
        supervisor = session["supervisor"]
        closed(supervisor, {"pid", "path", "sha256"}, "uzu_supervisor_identity_invalid")
        require(type(supervisor["pid"]) is int and isinstance(supervisor["path"], str)
                and Path(supervisor["path"]).is_absolute() and sha(supervisor["sha256"]),
                "uzu_supervisor_identity_invalid")
        self._remember(Path(supervisor["path"]), supervisor["sha256"])
        for source in (Path(__file__), Path(local.__file__), Path(local.__file__).with_name("choice_protocol.py")):
            self._remember(source, local.digest(source))
        identity = copy.deepcopy(session)
        identity["adapter_sha256"] = local.digest(__file__)
        self.provenance.update(available=True, authentication="not_provided_by_uzu",
            backend_requested="metal", backend_observed=None,
            input_limit_scope="client_preparation_not_server_configuration",
            token_id_live_match=None, physical_forward_count=None, identity=identity,
            identity_sha256=hashlib.sha256(local._wire(identity)).hexdigest(),
            session_sha256=self._model["session_sha256"])

    def _guard(self):
        require_native_supervision(self._profile, self._profile_path)
        require({p.name for p in Path(self._session["model"]["path"]).iterdir()} == REQUIRED_FILES,
                "uzu_pack_inventory_changed")
        super()._guard()

    def _overflow_response(self, data):
        # Uzu rejects this before encoding. No llama.cpp regex or fake n_ctx.
        try:
            value = decode(data)
            error = value["error"]
            if (error.get("code") == "backend_error" and error.get("type") == "server_error"
                    and error.get("message") == "Input larger than model context size"):
                return value
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
        return None
