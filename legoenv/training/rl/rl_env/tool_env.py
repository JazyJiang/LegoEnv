"""Text-in, observations-out tool environment for one LegoEnv episode; no trainer dependency.

A trainer drives it with three calls (the interface the original RL run used):

    obs0, info, _ = env.reset(record=prompt_record)   # info['envlib_initial_messages'], info['tools']
    obs, reward, terminated, truncated, info = env.step(assistant_turn_text)
    ... = env.finalize_truncated('exceed_max_steps' | 'exceed_max_length')   # trainer-side limits

`step` takes the raw decoded assistant turn (reasoning, `</think>`, content, Qwen3-Coder
`<tool_call>` XML, end-of-turn token). If it contains tool calls they are executed and the
list of tool results is returned (reward 0, not terminated). Otherwise the episode ends:
the task verifier is evaluated on the final world state and the reward is 1.0 if it
accepts, else 0.0 (`_reward`; the optional penalties were all 0 in the reported run).
Environment-process failures end the episode with `info['envlib_infra_error']` set; a
trainer should drop such trajectories from the batch rather than score them 0.
"""
from __future__ import annotations
import time
from typing import Any, Optional
from .episode import EnvHost, EnvHostError
from .toolcall import parse_calls, split_turn
FINISH_REASONS = ('stop', 'max_turns', 'length', 'context', 'wall_cap', 'eos_other')
TRUNCATED = {'max_turns', 'length', 'context', 'wall_cap'}
METRIC_NAMES = ('envlib_reward', 'envlib_pass', 'envlib_verifier_error', 'envlib_infra_invalid', 'envlib_turns', 'envlib_tool_calls', 'envlib_invalid_calls', 'envlib_failed_calls', 'envlib_route_404', 'envlib_malformed_turns', 'envlib_teacher_pass8') + tuple((f'envlib_finish_{r}' for r in FINISH_REASONS))

def _unwrap(v):
    if isinstance(v, (list, tuple)) and len(v) == 1:
        return v[0]
    return v

class LegoEnvToolEnv:
    metric_names = METRIC_NAMES

    def __init__(self, envlib_root: str='', env_python: str='', wall_seconds: float=1800.0, tool_timeout_s: float=120.0, reset_timeout_s: float=300.0, invalid_call_penalty: float=0.0, invalid_penalty_cap: float=0.5, truncation_penalty: float=0.0, require_stop: bool=False, **_: Any) -> None:
        self.envlib_root = envlib_root or None
        self.env_python = env_python or None
        self.wall_seconds = float(wall_seconds)
        self.tool_timeout_s = float(tool_timeout_s)
        self.reset_timeout_s = float(reset_timeout_s)
        self.invalid_call_penalty = float(invalid_call_penalty)
        self.invalid_penalty_cap = float(invalid_penalty_cap)
        self.truncation_penalty = float(truncation_penalty)
        self.require_stop = bool(require_stop)
        self.host: Optional[EnvHost] = None
        self.record: dict = {}
        self.tools: list = []
        self.result: Optional[dict] = None

    def reset(self, seed: int=0, ppo_step: int=0, data: Optional[dict]=None, record: Optional[dict]=None):
        del seed, ppo_step
        self.close()
        if record is None:
            payload = data or {}
            record = _unwrap(payload.get('metadata'))
        if not isinstance(record, dict) or 'tid' not in record:
            raise ValueError('LegoEnvToolEnv.reset needs a prompt record (metadata with tid/task_path/spec_path)')
        self.record = dict(record)
        self.turns = 0
        self.n_calls = self.n_invalid = self.n_malformed = 0
        self.transcript: list = []
        self.result = None
        self._done = False
        self._t0 = time.monotonic()
        self.host = EnvHost(self.envlib_root, self.env_python)
        r = self.host.reset(self.record, timeout=self.reset_timeout_s)
        self.tools = r['tools']
        self.initial_messages = [{'role': 'system', 'content': r['system']}, {'role': 'user', 'content': r['user']}]
        info = {'envlib_initial_messages': self.initial_messages, 'tools': self.tools, 'envlib_tid': self.record['tid'], 'envlib_tools_info': r.get('tools_info')}
        return (r['user'], info, False)

    def close(self) -> None:
        if self.host is not None:
            self.host.close()
            self.host = None

    def step(self, action: str, tool_call_parse_result=None, reasoning_parse_result=None):
        del tool_call_parse_result, reasoning_parse_result
        if self._done or self.host is None:
            raise RuntimeError('LegoEnvToolEnv is not active')
        self.turns += 1
        reasoning, normal, ended, eos = split_turn(action)
        if not ended:
            return self._finish('length')
        if eos != '<|im_end|>':
            return self._finish('eos_other')
        content, calls = parse_calls(normal, self.tools)
        if not calls:
            if '<tool_call>' in normal:
                self.n_malformed += 1
            return self._finish('stop')
        obs_list = []
        try:
            for c in calls:
                obs, info = self.host.call(c['name'], c['arguments'], timeout=self.tool_timeout_s)
                self.n_calls += 1
                if info.get('invalid'):
                    self.n_invalid += 1
                obs_list.append(obs)
                self.transcript.append((c['name'], c['arguments'], obs))
        except EnvHostError as e:
            return self._infra(e)
        if time.monotonic() - self._t0 > self.wall_seconds:
            return self._finish('wall_cap')
        return (obs_list, 0.0, False, False, {'use_tool': True, 'valid': True, 'envlib_n_calls': len(calls)})

    def finalize_truncated(self, reason: str):
        if self._done or self.host is None:
            return ('', 0.0, True, False, self._info(self.result or {}, 0.0))
        return self._finish({'exceed_max_steps': 'max_turns', 'exceed_max_length': 'context'}.get(reason, reason))

    def _metrics(self, res, reward):
        m = {k: 0.0 for k in METRIC_NAMES}
        st = res.get('stats') or {}
        m.update(envlib_reward=float(reward), envlib_pass=float(res.get('pass') is True), envlib_verifier_error=float(bool(res.get('verifier_error'))), envlib_infra_invalid=float(bool(res.get('infra_error'))), envlib_turns=float(self.turns), envlib_tool_calls=float(self.n_calls), envlib_invalid_calls=float(self.n_invalid), envlib_failed_calls=float(st.get('n_failed_calls', 0)), envlib_route_404=float(st.get('n_route_404', 0)), envlib_malformed_turns=float(self.n_malformed), envlib_teacher_pass8=float(self.record.get('teacher_pass8', 0) or 0))
        fr = res.get('finish')
        if fr in FINISH_REASONS:
            m[f'envlib_finish_{fr}'] = 1.0
        return m

    def _info(self, res, reward):
        info = {'use_tool': False, 'valid': True, 'metrics': self._metrics(res, reward), 'metrics_agg_mode': {k: 'last' for k in METRIC_NAMES}}
        if res.get('infra_error'):
            info['envlib_infra_error'] = res['infra_error']
        return info

    def _reward(self, passed, reason):
        r = 1.0 if passed else 0.0
        if self.require_stop and reason != 'stop':
            r = 0.0
        if self.invalid_call_penalty:
            r -= min(self.invalid_penalty_cap, self.invalid_call_penalty * self.n_invalid)
        if self.truncation_penalty and reason in TRUNCATED:
            r -= self.truncation_penalty
        return r

    def _finish(self, reason):
        self._done = True
        try:
            v = self.host.verify()
        except EnvHostError as e:
            return self._infra(e, reason)
        finally:
            self.close()
        passed = v.get('pass') is True
        reward = self._reward(passed, reason)
        self.result = {'finish': reason, 'pass': passed, 'verifier_error': v.get('verifier_error'), 'stats': v.get('stats') or {}, 'reward': reward, 'turns': self.turns}
        return ('', reward, True, False, self._info(self.result, reward))

    def _infra(self, err, reason=None):
        self._done = True
        self.close()
        self.result = {'finish': reason, 'pass': False, 'infra_error': str(err)[:2000], 'reward': 0.0, 'turns': self.turns}
        return ('', 0.0, True, False, self._info(self.result, 0.0))
__all__ = ['LegoEnvToolEnv', 'METRIC_NAMES', 'FINISH_REASONS']
