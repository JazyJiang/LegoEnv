# Training hyperparameters

The SFT and GRPO runs reported for LegoEnv were trained with an internal trainer that
is not part of this repository. This page records every setting that was written in
that trainer's run configurations and launchers, so the runs can be reproduced on any
SFT or RL stack. The environment-side code a trainer needs is in this directory: the
SFT exporter (`sft/tools/`) and the RL environment interface (`rl/`, see
[RL environment interface](../docs/rl.md)).

"framework default (not recorded)" means the run configuration did not set the value
and the trainer's default applied; it is not known from the recorded files.

## SFT: settings shared by every run

All SFT runs combined a base configuration (one per base model) with the 64K-context
preset, the length-grouping preset and one data preset (next table).

| Setting | Value |
|---|---|
| Base models | Qwen3.5-27B (`qwen35_27b`), Qwen3.6-27B (`qwen36_27b`), Qwen3.8-27B (`qwen38_27b`); full fine-tuning of the language model, vision tower and projector frozen, MTP off |
| Sequence length | 65,536 tokens (64K preset; the base configuration alone sets 32,768) |
| Samples longer than the sequence length | dropped, never truncated |
| Padding | each step padded to a multiple of 4,096 tokens (data presets; base configuration 512) |
| Length grouping | samples of one optimizer step drawn from the same 4,096-token length bucket (data presets; the grouping preset alone sets 2,048) |
| Epochs | 3 |
| Global / micro batch | 32 sequences (data presets; base configuration 64) / 1 |
| Optimizer | Adam, beta1 0.9, beta2 0.95, epsilon 1e-8 |
| Learning rate | 1e-5 peak, cosine decay to 1e-6 |
| Warmup | 3 steps (data presets; the base configuration also carries a 0.04 warmup fraction, the trainer's precedence between the two is not recorded) |
| Weight decay | 0.1 |
| Gradient clipping | max norm 1.0 |
| Loss | token-level cross entropy, averaged per token |
| Loss mask | every assistant turn is trained from after `<\|im_start\|>assistant\n<think>\n` (or after the header when there is no `<think>`) through `<\|im_end\|>\n`: reasoning, `</think>`, content and tool-call XML. System, user and tool-result tokens and the generation-prompt prefix are not trained. An assistant message with `step_loss_mask` other than 1 stays in the input with no loss |
| Rendering | the base model's own Hugging Face chat template with the exported `tools` list |
| Reasoning preservation | `preserve_thinking` false (chat-template default) except `ours2229`, which passes `preserve_thinking=true` |
| Precision | framework default (not recorded) |
| Parallelism | 8 GPUs per node; tensor parallel 2, pipeline parallel 4, context parallel 4 (64K preset), sequence parallel on, expert parallel 1 |
| Activation recomputation | full, uniform, 1 layer |
| Data order | shuffled, sampler seed 42; training seed 42 |
| Checkpointing | `save_interval` steps (data presets); optimizer state saved; online Hugging Face export |
| Evaluation during training | none (`eval_interval` 0) |

## SFT: data presets

Each preset names its corpus file (`train_<preset>.jsonl`). The Qwen3.5 variant
(`<preset>_q35`) changes only the corpus file to `train_<preset>_q35.jsonl`, the same
episodes with `None`-valued tool arguments rewritten to the string `"null"` by
`sft/tools/derive_q35.py`; every other value comes from the preset it is combined with.

| Preset | Corpus file (Qwen3.5 variant) | Corpus size | Global batch | Epochs | LR (schedule) | Warmup steps | Save interval (steps) | `preserve_thinking` | Recorded checkpoint |
|---|---|---|---|---|---|---|---|---|---|
| `r0a` | `train_r0a.jsonl` (`train_r0a_q35.jsonl`) | not recorded | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 39 | false | not recorded |
| `a` | `train_a.jsonl` (`train_a_q35.jsonl`) | not recorded | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 69 | false | not recorded |
| `s1k` | `train_s1k.jsonl` (`train_s1k_q35.jsonl`) | not recorded | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 100 | false | not recorded |
| `s2k` | `train_s2k.jsonl` (`train_s2k_q35.jsonl`) | not recorded | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 132 | false | not recorded |
| `s3k` | `train_s3k.jsonl` (`train_s3k_q35.jsonl`) | 5,229 trajectories (s3k v2) | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 163 | false | Qwen3.5-27B, step 489 (released) |
| `main` | `train_main.jsonl` (`train_main_q35.jsonl`) | 6,110 trajectories | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 190 | false | Qwen3.6-27B, step 570 (released) |
| `mainfix` | `train_mainfix.jsonl` (`train_mainfix_q35.jsonl`) | not recorded | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 220 | false | not recorded |
| `ours2229` | `train_ours2229.jsonl` (no Qwen3.5 variant) | 2,229 trajectories | 32 | 3 | 1e-5 to 1e-6 (cosine) | 3 | 69 | true | not recorded |

Total step counts are recorded only for the two released checkpoints. A one-node smoke
preset (8,192 tokens, batch 8, 1 epoch, 5 steps, warmup fraction 0.2, 48 samples, no
checkpoints, context parallel 1) was used for launch checks only.

## GRPO

| Setting | Value |
|---|---|
| Base model | original Qwen3.8-27B (not an SFT checkpoint); also the reference model |
| Prompts | 1,516 packs, selected by `rl/build_prompts.py`; prompt sampler seed 42 |
| Group size | 8 samples per prompt, all 8 kept |
| Prompts / trajectories per step | 12 prompts, 96 trajectories (training batch 96, micro batch 1) |
| Schedule | 2 epochs, 252 updates in total |
| Released checkpoint | update 200 of 252; checkpoints every 40 updates |
| Context length | 65,536 tokens; padding multiple 512 |
| Max turns | 100 assistant turns per episode |
| Max tokens per turn | 16,384 |
| Episode limits | 1,800 s wall time, 120 s per tool call, 300 s for environment reset |
| Reasoning | thinking enabled; each turn's generated tokens, reasoning included, stay in the episode context |
| Reward | 1 if the task verifier accepts the final world state, else 0; invalid-call penalty 0 (cap 0.5), truncation penalty 0, no stop requirement. Episodes whose environment process failed are masked out of the batch, not scored 0 |
| Advantage | GRPO, epsilon 1e-4 |
| Policy loss | ratio clip 0.2 |
| KL | GRPO KL loss coefficient 0.0 |
| Entropy bonus | framework default (not recorded) |
| Optimizer | Adam, beta1 0.9, beta2 0.999, epsilon 1e-8; weight decay 0.0; gradient clipping max norm 1.0 |
| Learning rate | 5e-7, cosine decay, warmup fraction 0.02; scheduler not restored from checkpoint |
| Precision | framework default (not recorded) |
| Sampling | vLLM; temperature 1.0, top-p 0.95, top-k 20, min-p 0.0, presence penalty 0.0, repetition penalty 1.0, no fixed sampling seed |
| Rollout | asynchronous, staleness at most 1 update; up to 96 concurrent episodes, 12 rollout workers, up to 16 trajectories per environment worker |
| Inference engine | tensor parallel 4, GPU memory utilization 0.85, at most 64 running requests, prefix caching on, at most 16,384 batched tokens |
| GPUs | 128: 8 nodes x 8 GPUs for the policy (tensor parallel 2, pipeline parallel 2, context parallel 4; full uniform recomputation, 1 layer) and 8 nodes x 8 GPUs for rollout; no separate critic or reward model |
| Batch balancing | sequence-length balancing across data-parallel ranks; dynamic micro-batching for forward-only passes (8,192-token target, at most 16 per micro batch) |
| Tool interface | `api_search`, `api_fetch`, `base64_encode` (historical schemas in `rl/envlib/collect_oai.py`); tool calls parsed from the policy's text, not by the inference engine |

Sources: values were read from the run configurations and launchers at commit
`1273dba` (SFT base configurations `qwen27b_sft.yaml`, `qwen35_27b.yaml`,
`qwen36_27b.yaml`, `qwen38_27b.yaml`; presets `exp/{r0a,a,s1k,s2k,s3k,main,mainfix,ours2229}.yaml`,
their `_q35` variants, `exp/seq64k.yaml`, `exp/glen.yaml`, `exp/smoke_1node.yaml`;
the SFT launcher and the training subcommand of `tools/pipeline.py` for the preset
combination; the SFT data module for the loss mask, rendering, `preserve_thinking`
default and over-length handling; GRPO configuration `grpo_q38_128h20.yaml` and its
launcher; the GRPO environment adapter for the reward and the trajectory manager for the episode context), and from
[`docs/models.md`](../docs/models.md) and the GRPO recipe in
[`docs/rl.md`](../docs/rl.md) at the same commit for corpus sizes, the 1,516 prompts,
the 252-update schedule and released checkpoint steps.
