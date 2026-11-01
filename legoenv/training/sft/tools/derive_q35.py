#!/usr/bin/env python3
"""train_v0.jsonl -> train_v0_q35.jsonl for the Qwen3.5 run (same episodes, same masks).

Why: api_fetch's params/body are `anyOf [string, null]` and the teacher (Qwen3.5-397B) wrote the
literal text `null` for them (the qwen3coder parser turns that into JSON null; writing `None`
instead arrives as the string "None" -> the 400 "Invalid JSON" turns we mask). The Qwen3.8 chat
template renders a None argument with tojson -> `null` (= what the teacher actually wrote), but
the Qwen3.5 template renders it with |string -> `None`, i.e. it would TRAIN the 3.5 student to emit
exactly the failing form in ~500 unmasked turns. Replacing None-valued tool-call arguments with
the string "null" makes the 3.5 rendering byte-identical to the 3.8 rendering of every assistant
turn. Nothing else changes; "None" STRING arguments
(the real failures, all in masked turns) are left as they are.

    python3 tools/derive_q35.py data/train_v0.jsonl data/train_v0_q35.jsonl
"""
import json
import os
import sys


def main(src, dst):
    n_eps = n_args = n_turns = 0
    tmp = dst + ".tmp"
    with open(src) as fi, open(tmp, "w") as fo:
        for line in fi:
            if not line.strip():
                continue
            rec = json.loads(line)
            k_ep = 0
            for m in rec["messages"]:
                hit = False
                for tc in m.get("tool_calls") or []:
                    args = tc["function"]["arguments"]
                    for k, v in list(args.items()):
                        if v is None:
                            args[k] = "null"
                            k_ep += 1
                            hit = True
                n_turns += hit
            rec.setdefault("meta", {})["q35_null_args"] = k_ep
            n_args += k_ep
            n_eps += 1
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, dst)
    print(json.dumps({"episodes": n_eps, "null_args_rewritten": n_args, "turns_touched": n_turns, "out": dst}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
