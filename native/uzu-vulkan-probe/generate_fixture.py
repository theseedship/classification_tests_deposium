#!/usr/bin/env python3
"""Create a tiny synthetic Uzu DecisionModel fixture, without inference or downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REVISION = "95e8f2282daf0fb78938b620f835b8fd3d716c73"
DIM = 64


def norm():
    return dict(epsilon=1e-6, scale_offset=None, upcast_mode="full_layer",
                subtract_mean=False, has_scale=False, has_biases=False)


def config():
    attention = dict(type="AttentionConfig", qkvg_projection_config={}, out_projection_config={},
                     query_norm_config=None, key_norm_config=None, num_heads=1, num_groups=1,
                     head_dim=DIM, is_causal=True, scale=None, sliding_window_size=None,
                     logit_soft_cap=None, has_sinks=False, has_qkvg_biases=False,
                     has_out_biases=False, has_gate=False, normalize_values=False, is_kv_sharing=False)
    layer = dict(pre_mixer_norm_config=norm(), mixer_config=attention, mixer_conv_config=None,
                 post_mixer_norm_config=None, pre_mlp_norm_config=norm(),
                 mlp_config=dict(type="DenseMLPConfig", linear_config={}, activation=dict(type="SiLU", alpha=1.0),
                                 has_up_biases=False, has_down_biases=False, gate_clipping=None, up_clipping=None),
                 mlp_conv_config=None, post_mlp_norm_config=None, hidden_dim=None, ple_config=None,
                 has_post_layer_scalar=False, kv_source_layer_index=None, rope_config=None)
    generation = {key: None for key in ("temperature", "top_k", "top_p", "min_p", "banned_tokens",
                                         "repetition_penalty", "presence_penalty", "frequency_penalty",
                                         "suffix_repetition_length")}
    generation["stop_token_ids"] = []
    return dict(type="DecisionModelConfig", token_codec_config=dict(type="RawTextCodecConfig"),
                decoder_config=dict(embedding_config=dict(type="UntiedEmbeddingConfig", input_scale=None,
                                                          logit_soft_cap=None, logit_scale=None),
                                    transformer_config=dict(layer_configs=[layer], output_norm_config=norm(),
                                                            model_dim=DIM, hidden_dim=DIM),
                                    vocab_size=2, ple_model_config=None, embedding_norm_config=None),
                generation_config=generation, decision=dict(codes=["a", "b"], temperature=1.0))


def tensors():
    """Small dyadic values are exactly representable in BF16; no learned weights."""
    pattern = [1.0 if i % 2 == 0 else 0.5 for i in range(DIM)]
    yield "decoder.embedding.input_embedding.weights", "BF16", [2, DIM], pattern + [-x for x in pattern]
    yield "decoder.embedding.output_embedding.weights", "F32", [2, DIM], [x / DIM for x in pattern] + [-x / DIM for x in pattern]
    prefix = "decoder.transformer.layers.0."
    for name, rows, scale in (("mixer.qkvg_projection", 3 * DIM, 0.25),
                               ("mixer.out_projection", DIM, 0.25),
                               ("mlp.up_projection", 2 * DIM, 0.125),
                               ("mlp.down_projection", DIM, 0.125)):
        values = [scale if row % DIM == column else 0.0 for row in range(rows) for column in range(DIM)]
        yield prefix + name + ".weights.weights", "BF16", [rows, DIM], values


def safetensors_bytes():
    header, payload, metadata = {}, bytearray(), {}
    for name, dtype, shape, values in tensors():
        start = len(payload)
        for value in values:
            raw = struct.pack("<f", value)
            payload.extend(raw[2:] if dtype == "BF16" else raw)
        header[name] = dict(dtype=dtype, shape=shape, data_offsets=[start, len(payload)])
        layout = "input_output" if name.startswith("decoder.embedding.input_embedding.") else "output_input"
        metadata[name.removesuffix("weights") + "spec"] = json.dumps(dict(type="FullPrecisionSpec", layout=layout), sort_keys=True)
    header["__metadata__"] = metadata
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 8)
    return struct.pack("<Q", len(encoded)) + encoded + payload


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def generate(output):
    output = Path(output).resolve()
    results = (ROOT / "results").resolve()
    if output == results or not output.is_relative_to(results):
        raise ValueError("output_must_be_new_directory_under_results")
    if output.exists():
        raise ValueError("output_already_exists")
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--quiet", "--no-index",
                              str(output / "fixture.json")], capture_output=True, timeout=15)
    if ignored.returncode != 0:
        raise ValueError("output_not_ignored")
    tokenizer = dict(version="1.0", truncation=None, padding=None, added_tokens=[], normalizer=None,
                     pre_tokenizer=None, post_processor=None, decoder=None,
                     model=dict(type="WordLevel", vocab={"[UNK]": 0, "synthetic": 1}, unk_token="[UNK]"))
    files = {"config.json": json_bytes(config()), "tokenizer.json": json_bytes(tokenizer),
             "model.safetensors": safetensors_bytes()}
    receipt = dict(schema_version="deposium.uzu-vulkan-synthetic-fixture/v1", source_revision=SOURCE_REVISION,
                   provenance="Agent-authored synthetic arithmetic weights; no pretrained weights or semantic reference.",
                   qualification="Fixture structure only; not a model capability result or passing reference.",
                   campaign="not_run", cases_scored=0, expected_probabilities=None,
                   inputs=[[0], [1], [0, 1], [1, 0]], option_count=2,
                   negative_controls=[dict(input=[], option_count=2, expected_error="EmptyInput"),
                                      dict(input=[0], option_count=0, expected_error="InvalidOptionCount"),
                                      dict(input=[0], option_count=3, expected_error="InvalidOptionCount")],
                   tensors=[dict(name=name, dtype=dtype, shape=shape) for name, dtype, shape, _ in tensors()],
                   files_sha256={name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                   generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (output / name).write_bytes(data)
    (output / "fixture.json").write_bytes(json_bytes(receipt))
    return dict(status="synthetic_fixture_written", tensor_count=len(receipt["tensors"]),
                campaign="not_run", cases_scored=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = generate(args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "fixture_write_error"
        print(json.dumps(dict(status="error", reason=reason)))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
