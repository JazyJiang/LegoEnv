#!/usr/bin/env python3
"""Check the RL environment interface before training, without a model or a trainer.

Pack files readable, the env host starts with this interpreter, and for N packs: the
reference (witness) replay scores reward 1.0 and a no-op scores 0.0 through the same
LegoEnvToolEnv object a trainer drives. With --tokenizer, also checks that the chat
template renders a tool turn prefix-stably (needs transformers)."""
import argparse
import json
import os
import sys
import time

RL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--tokenizer", help="HF model/tokenizer dir; omit to skip the chat-template check")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    from rl_env import paths
    from rl_env.local_rollout import GoldPolicy, NoopPolicy, run_episode
    from rl_env.render import TurnRenderer
    t0 = time.time()
    recs = [json.loads(l) for l in open(paths.resolve(a.prompts), encoding="utf-8") if l.strip()]
    print(f"[selfcheck] {len(recs)} prompts in {a.prompts}; python {sys.version.split()[0]}", flush=True)
    missing = [r["tid"] for r in recs if not os.path.exists(paths.resolve(r["spec_path"]))]
    if missing:
        print(f"[selfcheck] FAIL: {len(missing)} pack files missing, e.g. {missing[:3]}")
        return 1
    cand = [r for r in recs if r.get("gold_ok", True)][: a.n]
    for r in cand:
        pol = GoldPolicy()
        res, _ = run_episode(r, pol, max_turns=400)
        noop, _ = run_episode(r, NoopPolicy(), max_turns=2)
        print(f"[selfcheck] {r['tid']}: gold reward={res.get('reward')} finish={res.get('finish')} "
              f"turns={res.get('turns')} | noop reward={noop.get('reward')}", flush=True)
        if res.get("reward") != 1.0 or noop.get("reward") != 0.0:
            print(f"[selfcheck] FAIL on {r['tid']}: {res} / {noop}")
            return 1
    if not cand:
        print("[selfcheck] FAIL: no prompt with gold_ok")
        return 1
    if not a.tokenizer:
        print(f"[selfcheck] OK in {time.time() - t0:.1f}s (chat-template check skipped)")
        return 0
    # the chat template renders a tool turn prefix-stably for this tokenizer
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(paths.resolve(a.tokenizer), trust_remote_code=True)
    from rl_env.episode import EnvHost
    h = EnvHost()
    try:
        rs = h.reset(cand[0])
    finally:
        h.close()
    rr = TurnRenderer(tok, [{"role": "system", "content": rs["system"]}, {"role": "user", "content": rs["user"]}], rs["tools"])
    n0 = len(rr.first_prompt_ids())
    delta = rr.tool_turn_text(["{\"ok\": true}"])
    assert delta.startswith("\n<|im_start|>") and delta.endswith("<think>\n"), repr(delta[:80] + " ... " + delta[-40:])
    print(f"[selfcheck] OK in {time.time() - t0:.1f}s (first prompt {n0} tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
