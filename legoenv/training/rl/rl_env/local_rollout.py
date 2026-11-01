"""Framework-free episode loop for checks and examples: run_episode(record, policy).

A policy is any callable `policy(env, messages) -> (turn_text, assistant_message)`:
`turn_text` is what a model would have generated (fed to `LegoEnvToolEnv.step`), and
`assistant_message` is the same turn as an OpenAI-style message for the running history.
GoldPolicy replays the task's reference solution (reward 1 expected), NoopPolicy ends at
once (reward 0 expected), RandomPolicy issues random calls. To roll out a real model,
wrap its generation call in the same signature.
"""
from __future__ import annotations
import json
import random
from typing import Protocol
from .tool_env import LegoEnvToolEnv
END = '<|im_end|>'

def qwen_turn_text(reasoning, content='', calls=()):
    out = f'{reasoning}\n</think>\n\n'
    if content:
        out += content.strip()
    for i, c in enumerate(calls):
        if content or i:
            out += '\n'
        out += f"<tool_call>\n<function={c['name']}>\n"
        for k, v in (c.get('arguments') or {}).items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            elif v is None:
                v = 'null'
            elif isinstance(v, bool):
                v = 'true' if v else 'false'
            out += f'<parameter={k}>\n{v}\n</parameter>\n'
        out += '</function>\n</tool_call>'
    return out + END

class Policy(Protocol):

    def __call__(self, env: LegoEnvToolEnv, messages: list) -> tuple:
        ...

class GoldPolicy:

    def __init__(self, renderer=None):
        self.i = 0
        self.renderer = renderer

    def __call__(self, env, messages):
        g = env.host.gold_next(self.i)
        if g.get('done'):
            msg = {'role': 'assistant', 'reasoning_content': 'All witness steps are done.', 'content': 'Done: every requested change has been made.'}
            calls = []
        else:
            self.i += 1
            calls = [{'name': g['name'], 'arguments': g['arguments']}]
            msg = {'role': 'assistant', 'reasoning_content': f"Gold step {self.i}: {g.get('tool')}.", 'content': '', 'tool_calls': [{'id': f'call_{self.i}', 'type': 'function', 'function': {'name': c['name'], 'arguments': c['arguments']}} for c in calls]}
        if self.renderer is not None:
            return (self.renderer.assistant_turn_text(messages, msg), msg)
        return (qwen_turn_text(msg['reasoning_content'], msg.get('content', ''), calls), msg)

class NoopPolicy:

    def __call__(self, env, messages):
        msg = {'role': 'assistant', 'reasoning_content': 'Nothing to do.', 'content': 'I have completed the task.'}
        return (qwen_turn_text(msg['reasoning_content'], msg['content']), msg)

class RandomPolicy:
    WORDS = ['list', 'create', 'update', 'delete', 'user', 'ticket', 'invoice', 'meeting', 'email', 'task', 'row', 'contact', 'order', 'project', 'message', 'record', 'send', 'get']

    def __init__(self, seed=0, n_calls=6):
        self.rng = random.Random(seed)
        self.left = n_calls
        self.urls = []

    def __call__(self, env, messages):
        if self.left <= 0:
            return NoopPolicy()(env, messages)
        self.left -= 1
        if not self.urls or self.rng.random() < 0.4:
            q = ' '.join(self.rng.sample(self.WORDS, 2))
            call = {'name': 'api_search', 'arguments': {'query': q, 'top_k': 5}}
        else:
            url = self.rng.choice(self.urls)
            body = {self.rng.choice(self.WORDS): self.rng.choice(self.WORDS + [1, 2, 3])}
            call = {'name': 'api_fetch', 'arguments': {'method': self.rng.choice(['POST', 'PATCH', 'DELETE', 'GET']), 'url': url, 'params': None, 'body': json.dumps(body)}}
        msg = {'role': 'assistant', 'reasoning_content': 'random', 'content': '', 'tool_calls': [{'id': 'r', 'type': 'function', 'function': call}]}
        return (qwen_turn_text('random', '', [call]), msg)

    def observe(self, obs_list):
        import re
        for o in obs_list:
            self.urls += re.findall('https?://[^\\s\\"\'<>]+', o)[:5]

def run_episode(record, policy, env_kwargs=None, max_turns=100, env=None):
    env = env or LegoEnvToolEnv(**env_kwargs or {})
    try:
        _, info, _ = env.reset(record=record)
        messages = [dict(m) for m in info['envlib_initial_messages']]
        transcript = []
        for _turn in range(max_turns):
            text, msg = policy(env, messages)
            obs, reward, term, trunc, sinfo = env.step(text)
            messages.append(msg)
            transcript.append({'role': 'assistant', 'text': text})
            if term:
                break
            for i, o in enumerate(obs):
                messages.append({'role': 'tool', 'tool_call_id': f'call_{i}', 'content': o})
                transcript.append({'role': 'tool', 'content': o})
            if hasattr(policy, 'observe'):
                policy.observe(obs)
        else:
            env.finalize_truncated('exceed_max_steps')
        return (env.result, transcript)
    finally:
        env.close()
