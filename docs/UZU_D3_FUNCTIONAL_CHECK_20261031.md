# Uzu d3-flash-M: local functional API check

31 October 2026. **The official Uzu/Mirai CLI served a locally staged d3-flash-M
pack through its own loopback API.** One synthetic request received valid
choice, yes/no and ordered-score responses. The process group was stopped and
its absence and refused API connection were checked afterward.

This is an unscored functional check, not a dataset campaign, a benchmark or
a product qualification. No historical corpus, reference, score or archive was
changed, and no new result row belongs in the generated leaderboard.

## Public identities

| Input | Identity |
|---|---|
| Official portable Apple Silicon CLI | [Mirai/Uzu release 0.6.15](https://github.com/trymirai/uzu/releases/tag/0.6.15), `mirai-aarch64-apple-darwin.tar.gz` |
| Archive SHA-256 | `59ae1ced82ee82f6caaa6f476c8422a4a87099f7ca2d032fe13e4e6633d6a743` |
| Executable SHA-256 | `c3e5798127eb037f6b8571817203096ab8a1ae4bcd24a06b951a25d044896f21`, reports `cli 0.6.15` |
| Pack | [trymirai/d3-flash-M@86f617b6](https://huggingface.co/trymirai/d3-flash-M/tree/86f617b67e3f0ce02fe678c38801e2296a303777), text-only Mirai-M |
| Weight-file SHA-256 | `dcf55ac5fdda40f5d13e4b504770e3de32b5db463f8135382f5f4e8adbfb8469` |
| Weight-file bytes | 4,295,274,576; file size is not runtime RAM |

The six staged runtime files were checked against pinned public metadata and
their local hashes. The official release binary is a distinct identity from a
locally built candidate at the source revision in the prospective controller;
version matching alone does not establish source/binary equivalence.

## Observed operation

The stock CLI was started with a local pack directory, `server`, explicit
`--host 127.0.0.1` and `--no-prefix-cache`. `GET /v1/models` returned the single
served ID `d3-flash-M`. `POST /v1/systemone` returned HTTP 200 for three questions
about this synthetic state:

> The customer was billed twice for the same order. They have a receipt.
> They need the refund today.

| Question type | Returned result |
|---|---|
| Choice: billing / technical / sales | `billing`, probability 0.9998243451 |
| Yes/no: does the customer have a receipt? | Yes probability 0.9989323020 |
| Score: routine / within a week / today | Expected level 1.9733816870 on 0–2; Today probability 0.9822260141 |

All declared probability distributions were finite, in 0–1 and summed to one
within the existing numerical tolerance. Usage reported 370 input tokens across
the questions and zero generated tokens. This is not a measured physical-forward
count. The check did not invoke the corpus scorer or assess general model quality.

## Startup failures retained and controller correction

Two earlier starts failed before returning any model answer:

1. The proposed macOS SBPL policy used `127.0.0.1` where `remote ip` accepts
   the special host form `localhost` or wildcard; the OS rejected the policy.
2. Correcting that syntax exposed an initialization request to
   `https://sdk.trymirai.com/api/v1/fetch/models`, denied by the outbound policy,
   even though the selected weights were a verified local directory.

The third start permitted normal outbound bootstrap and succeeded. The API
still listened on IPv4 loopback, but **offline operation and network egress
isolation were not established**. The controller now uses the stock local CLI
command and records `egress_isolated:false`; it must not claim an offline launch.
Verified local pack files, restricted child environment, served-ID checks,
supervision, input receipts and cleanup checks remain required.

The unsuccessful attempts and successful response/closure receipts remain in
separate local evidence folders. No user application, running benchmark or
unrelated process was stopped. Raw path-bearing files are not published here.

## Limits and next step

The functional attempt deliberately ran without a timing-isolation window.
No latency, memory saving, fit, Metal-device observation or Memfit gain is claimed.
The full controller's source-bound native input-preparation producer and pinned
runtime remain prerequisites for a separate, coordinated comparison. The native
release check does not complete those controller gates or qualify offline
embedding in an application. See the [CPU contribution](UZU_DECISION_CPU_20261031.md).
