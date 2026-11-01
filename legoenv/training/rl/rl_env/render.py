"""Token-level rendering of an episode with the policy's Hugging Face chat template.

A multi-turn RL trajectory is one token sequence:

    first_prompt_ids() + response_1 + tool_turn_ids(obs_1) + response_2 + ... + response_n

`response_k` are the tokens the policy generated (reasoning included, so reasoning stays
in context across turns); only they carry loss. `tool_turn_ids(obs)` renders the tool
results of one turn plus the next assistant header, as the template would render them
after an assistant turn, without re-tokenizing the generated tokens. Construction checks
that the template is prefix-stable across a tool turn. Needs only a tokenizer object with
`apply_chat_template` and `__call__` (transformers).
"""
END = '<|im_end|>'

def render_text(tokenizer, messages, tools, add_generation_prompt):
    out = tokenizer.apply_chat_template(messages, tools=tools or None, tokenize=False, add_generation_prompt=add_generation_prompt)
    if not isinstance(out, str):
        out = out[0]
    return out

def encode(tokenizer, text):
    return list(tokenizer(text, add_special_tokens=False)['input_ids'])

class TurnRenderer:

    def __init__(self, tokenizer, initial_messages, tools):
        self.tok = tokenizer
        self.base = [dict(m) for m in initial_messages]
        self.tools = tools
        name = tools[0]['function']['name'] if tools else 'noop'
        self._dummy = {'role': 'assistant', 'content': '', 'reasoning_content': 'placeholder', 'tool_calls': [{'id': 'call_0', 'type': 'function', 'function': {'name': name, 'arguments': {}}}]}
        self._a = render_text(tokenizer, self.base + [self._dummy], tools, False)
        k = self._a.rfind(END)
        if k < 0:
            raise ValueError('chat template does not end assistant turns with <|im_end|>')
        self._lead = self._a[k + len(END):]

    def first_prompt_text(self):
        return render_text(self.tok, self.base, self.tools, True)

    def first_prompt_ids(self):
        return encode(self.tok, self.first_prompt_text())

    def tool_turn_text(self, observations):
        msgs = self.base + [self._dummy] + [{'role': 'tool', 'tool_call_id': f'call_{i}', 'content': o} for i, o in enumerate(observations)]
        b = render_text(self.tok, msgs, self.tools, True)
        if not b.startswith(self._a):
            raise ValueError('chat template rendering is not prefix-stable across a tool turn')
        return self._lead + b[len(self._a):]

    def tool_turn_ids(self, observations):
        return encode(self.tok, self.tool_turn_text(observations))

    def assistant_turn_text(self, prior_messages, assistant_message):
        p = render_text(self.tok, prior_messages, self.tools, True)
        f = render_text(self.tok, prior_messages + [assistant_message], self.tools, False)
        if not f.startswith(p):
            raise ValueError('assistant rendering is not prefix-stable')
        t = f[len(p):]
        k = t.rfind(END)
        return t[:k + len(END)]
