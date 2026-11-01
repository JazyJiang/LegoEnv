"""RL prompt dataset: the JSONL written by build_prompts.py, one pack per line.

Each record needs `tid`, `task_path` and `spec_path` (optional `system_path`,
`pack_set`); relative paths resolve from training/rl/. A record is the whole prompt:
`LegoEnvToolEnv.reset(record=...)` builds the system and user messages and the tool
list from the pack. Standard library only; wrap it in your framework's dataset type.
"""
from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any, Iterator
try:
    from .paths import resolve
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rl_env.paths import resolve


class PromptDataset:

    def __init__(self, path: str) -> None:
        self.path = Path(resolve(path))
        if not self.path.is_file():
            raise FileNotFoundError(f'prompts JSONL not found: {self.path}')
        self.records: list[dict[str, Any]] = []
        with self.path.open(encoding='utf-8') as f:
            for ln, line in enumerate(f):
                if not line.strip():
                    continue
                rec = json.loads(line)
                for k in ('tid', 'task_path', 'spec_path'):
                    if k not in rec:
                        raise ValueError(f'{self.path}:{ln + 1}: missing {k}')
                self.records.append(rec)
        if not self.records:
            raise ValueError(f'prompts JSONL is empty: {self.path}')

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        rec = self.records[index]
        return {'metadata': rec, 'unique_id': f"{rec.get('pack_set', 'ours')}/{rec['tid']}"}

    def batches(self, prompts_per_step: int, seed: int = 42, epochs: int = 1, rank: int = 0,
                world: int = 1) -> Iterator[list[dict[str, Any]]]:
        """Seeded per-epoch shuffle, cut into steps of `prompts_per_step` records (the tail
        that does not fill a step is dropped); with world > 1 each rank gets a strided share
        of every step. The reported run used 12 prompts per step, seed 42, 2 epochs."""
        for epoch in range(epochs):
            order = list(range(len(self.records)))
            random.Random(seed * 1000003 + epoch).shuffle(order)
            for s in range(len(order) // prompts_per_step):
                step = order[s * prompts_per_step:(s + 1) * prompts_per_step]
                yield [self.records[i] for i in step[rank::world]]


__all__ = ['PromptDataset']
