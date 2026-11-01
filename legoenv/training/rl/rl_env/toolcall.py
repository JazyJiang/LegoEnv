"""Split a decoded assistant turn and parse its Qwen3-Coder style tool calls.

Format (what the Qwen3.5/3.6/3.8 chat templates render and the models emit):

    <tool_call>
    <function=api_fetch>
    <parameter=method>
    GET
    </parameter>
    ...
    </function>
    </tool_call>

Parameter values are text; they are converted with the tool's JSON schema in the way
the Qwen3-Coder tool parser does: the literal `null` becomes None; `string` stays text;
`integer`/`number`/`boolean` are converted; any other declared type (object, array) is
read as JSON, falling back to a Python literal, then to the raw text. A parameter with
no `type` (for example `anyOf`) is treated as a string. This is a standard-library
re-implementation; the reported run used the parser bundled with its trainer.
"""
import ast
import json
import re

EOS_MARKERS = ('<|im_end|>', '<|endoftext|>')
_CALL_RE = re.compile(r'<tool_call>(.*?)</tool_call>|<tool_call>(.*)$', re.S)
_FUNC_RE = re.compile(r'<function=(.*?)>(.*?)(?:</function>|$)', re.S)
_PARAM_RE = re.compile(r'<parameter=(.*?)>(.*?)(?:</parameter>|(?=<parameter=)|(?=</function>)|$)', re.S)


def split_turn(text):
    """-> (reasoning, normal_text, ended, eos). `ended` is False when no end-of-turn token
    closes the text (the generation hit its length limit)."""
    t = text
    eos = None
    stripped = t.rstrip('\n')
    for m in EOS_MARKERS:
        if stripped.endswith(m):
            eos = m
            t = stripped[:-len(m)]
            break
    if '</think>' in t:
        reasoning, _, normal = t.partition('</think>')
    else:
        reasoning, normal = (t, '')
    reasoning = reasoning.lstrip()
    if reasoning.startswith('<think>'):
        reasoning = reasoning[len('<think>'):]
    return (reasoning.strip('\n'), normal, eos is not None, eos)


def _schema_props(tools, name):
    for t in tools or []:
        f = t.get('function', t)
        if f.get('name') == name:
            return (f.get('parameters') or {}).get('properties') or {}
    return {}


def _convert(value, prop):
    if value.lower() == 'null':
        return None
    kind = str(prop.get('type', 'string')).strip().lower() if isinstance(prop, dict) else 'string'
    if kind in ('string', 'str', 'text', 'varchar', 'char', 'enum'):
        return value
    if kind.startswith(('int', 'uint', 'long', 'short', 'unsigned')):
        try:
            return int(value)
        except ValueError:
            return value
    if kind.startswith(('num', 'float', 'double')):
        try:
            f = float(value)
            return f if '.' in value or 'e' in value.lower() else int(f)
        except ValueError:
            return value
    if kind in ('boolean', 'bool', 'binary'):
        return value.lower() == 'true'
    try:
        return json.loads(value)
    except ValueError:
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value


def _strip_nl(s):
    if s.startswith('\n'):
        s = s[1:]
    if s.endswith('\n'):
        s = s[:-1]
    return s


def parse_calls(normal_text, tools):
    """-> (content, calls); calls = [{id, name, arguments: dict}]. Text before the first
    call is the content. Text without any call markup returns no calls."""
    if '<tool_call>' not in normal_text and '<function=' not in normal_text:
        return (normal_text.strip(), [])
    start = min(i for i in (normal_text.find('<tool_call>'), normal_text.find('<function=')) if i >= 0)
    content = normal_text[:start]
    rest = normal_text[start:]
    blocks = [a or b for a, b in _CALL_RE.findall(rest)] if '<tool_call>' in rest else [rest]
    calls = []
    for block in blocks:
        for name, body in _FUNC_RE.findall(block):
            name = name.strip()
            props = _schema_props(tools, name)
            args = {}
            for key, raw in _PARAM_RE.findall(body):
                key = key.strip()
                args[key] = _convert(_strip_nl(raw), props.get(key, {}))
            calls.append({'id': f'call_{len(calls)}', 'name': name, 'arguments': args})
    return (content.strip(), calls)
