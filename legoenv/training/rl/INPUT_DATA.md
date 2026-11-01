# Caller-provided RL inputs

The RL environment interface (`rl_env/`), the execution adapter (`envlib/`), the
prompt builder and the self-check are included; no trainer is. Historical prompt JSONL
files and seeded worlds are not included in this code component: their third-party
seed licences require separate clearance. Supply your own qualified task/spec list and
use build_prompts.py as described in `legoenv/docs/rl.md`. The settings of the
historical run are in `training/HYPERPARAMETERS.md`; that run and its weights are
unchanged. Missing historical data are not silently replaced with new examples.
