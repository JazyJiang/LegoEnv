# Released models

This page lists the three released checkpoints.

| Base | Released artifact | Training input | Epochs | Checkpoint |
|---|---|---|---|---|
| Qwen3.5-27B | `qwen3.5-27b-sft` | 5,229 SFT trajectories (round 1 + 3k draw) | 3 | step 489 |
| Qwen3.6-27B | `qwen3.6-27b-sft` | 6,110 SFT trajectories (round 2) | 3 | step 570 |
| Qwen3.8-27B | `qwen3.8-27b-grpo` | 1,516 RL prompts | 2 (GRPO) | step 200 |

The SFT checkpoints are final exports of full runs
([settings](../training/HYPERPARAMETERS.md#sft-data-presets)). The GRPO checkpoint is update 200 of a
252-update schedule ([settings](../training/HYPERPARAMETERS.md#grpo)). None of them was the teacher for
trajectory collection.

Weights are published on Hugging Face under [`JazySong`](https://huggingface.co/JazySong)
in the `LegoEnv` model repository, one folder per checkpoint (`qwen3.5-27b-sft`,
`qwen3.6-27b-sft`, `qwen3.8-27b-grpo`), each loadable with `transformers`. MTP layers
are not included.
