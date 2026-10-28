"""Explicit tokenizer-only process: no Torch, Julia import or model weights."""
from __future__ import annotations

import json
import sys

LIMIT = 1024 * 1024


def main():
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(sys.argv[1])
    print(json.dumps({"ready": True}), flush=True)
    while True:
        line = sys.stdin.buffer.readline(LIMIT + 1)
        if not line:
            break
        if len(line) > LIMIT:
            raise ValueError("tokenizer_input_limit")
        request = json.loads(line)
        if not isinstance(request, list) or not request or len(request) > 64:
            raise ValueError("tokenizer_batch_invalid")
        if any(not isinstance(item, str) for item in request):
            raise ValueError("tokenizer_input_invalid")
        print(json.dumps([len(tokenizer.encode(item, add_special_tokens=False).ids)
                          for item in request]), flush=True)


if __name__ == "__main__":
    main()
