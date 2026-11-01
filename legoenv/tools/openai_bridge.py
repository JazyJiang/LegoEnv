#!/usr/bin/env python3
"""Translate local Claude Code messages to standard OpenAI Chat Completions.

Upstream authentication uses only an optional Bearer key. Reasoning history is
an explicit extension for compatible self-hosted models, disabled by default.
"""
import argparse
import http.client
import http.server
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ProtocolError(ValueError):
    pass


def completion_url(base_url):
    parts = urllib.parse.urlsplit(base_url)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname or
            parts.username or parts.password or parts.query or parts.fragment):
        raise ProtocolError('Use an HTTP(S) API base without credentials, query or fragment')
    base = base_url.rstrip('/')
    return base if base.endswith('/chat/completions') else base + '/chat/completions'


def text_content(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ProtocolError('Expected text or text content blocks')
    result = []
    for block in value:
        if block.get('type') != 'text':
            raise ProtocolError('This code-agent bridge supports text content only')
        result.append(block.get('text', ''))
    return '\n'.join(result)


def to_openai(body, model, extra_body=None, forward_reasoning=False):
    messages = []
    if body.get('system'):
        messages.append({'role': 'system', 'content': text_content(body['system'])})
    for message in body['messages']:
        role, content = message['role'], message['content']
        if role not in {'user', 'assistant'}:
            raise ProtocolError('Unsupported local message role')
        blocks = [{'type': 'text', 'text': content}] if isinstance(content, str) else content
        if not isinstance(blocks, list):
            raise ProtocolError('Expected content blocks')
        if role == 'user':
            pending = []
            for block in blocks:
                if block.get('type') == 'tool_result':
                    if pending:
                        messages.append({'role': 'user', 'content': '\n'.join(pending)})
                        pending = []
                    messages.append({'role': 'tool', 'tool_call_id': block['tool_use_id'],
                                     'content': text_content(block.get('content', ''))})
                elif block.get('type') == 'text':
                    pending.append(block.get('text', ''))
                else:
                    raise ProtocolError('Unsupported user content block')
            if pending:
                messages.append({'role': 'user', 'content': '\n'.join(pending)})
        else:
            text, reasoning, calls = [], [], []
            for block in blocks:
                kind = block.get('type')
                if kind == 'text':
                    text.append(block.get('text', ''))
                elif kind == 'thinking':
                    reasoning.append(block.get('thinking', ''))
                elif kind == 'tool_use':
                    calls.append({'id': block['id'], 'type': 'function', 'function': {
                        'name': block['name'], 'arguments': json.dumps(block['input'], ensure_ascii=False)}})
                else:
                    raise ProtocolError('Unsupported assistant content block')
            converted = {'role': 'assistant', 'content': '\n'.join(text) or None}
            if calls:
                converted['tool_calls'] = calls
            if forward_reasoning and reasoning:
                converted['reasoning_content'] = '\n'.join(reasoning)
            messages.append(converted)
    payload = {'model': model, 'messages': messages, 'stream': bool(body.get('stream'))}
    for key in ['max_tokens', 'temperature', 'top_p']:
        if key in body:
            payload[key] = body[key]
    if body.get('stop_sequences'):
        payload['stop'] = body['stop_sequences']
    if body.get('tools'):
        payload['tools'] = []
        for tool in body['tools']:
            if not tool.get('name') or not isinstance(tool.get('input_schema'), dict):
                raise ProtocolError('Only function tools with explicit input schemas are supported')
            payload['tools'].append({'type': 'function', 'function': {
                'name': tool['name'], 'description': tool.get('description', ''),
                'parameters': tool['input_schema']}})
    choice = body.get('tool_choice') or {}
    if choice:
        kind = choice.get('type')
        if kind == 'tool':
            payload['tool_choice'] = {'type': 'function', 'function': {'name': choice['name']}}
        elif kind in {'auto', 'any', 'none'}:
            payload['tool_choice'] = {'any': 'required'}.get(kind, kind)
        else:
            raise ProtocolError('Unsupported tool choice')
        if 'disable_parallel_tool_use' in choice:
            payload['parallel_tool_calls'] = not choice['disable_parallel_tool_use']
    extra = extra_body or {}
    if not isinstance(extra, dict) or set(extra) & {'model', 'messages', 'tools', 'stream'}:
        raise ProtocolError('Extra body cannot replace model, messages, tools or stream')
    payload.update(extra)
    return payload


def stop_reason(reason):
    if reason not in {'stop', 'tool_calls', 'length'}:
        raise ProtocolError('Missing or unsupported upstream finish reason')
    return {'stop': 'end_turn', 'tool_calls': 'tool_use', 'length': 'max_tokens'}[reason]


def tool_block(call):
    function = call.get('function') or {}
    if not call.get('id') or not function.get('name'):
        raise ProtocolError('Incomplete upstream function identity')
    try:
        arguments = json.loads(function.get('arguments', '{}'))
    except (ValueError, TypeError):
        raise ProtocolError('Upstream function arguments are not valid JSON') from None
    if not isinstance(arguments, dict):
        raise ProtocolError('Function arguments must be a JSON object')
    return {'type': 'tool_use', 'id': call['id'], 'name': function['name'], 'input': arguments}


def to_message(result, model):
    choice = result['choices'][0]
    message = choice['message']
    blocks = []
    reasoning = message.get('reasoning_content') or message.get('reasoning')
    if reasoning:
        blocks.append({'type': 'thinking', 'thinking': reasoning, 'signature': ''})
    if message.get('content'):
        blocks.append({'type': 'text', 'text': text_content(message['content'])})
    blocks.extend(tool_block(c) for c in message.get('tool_calls', []))
    usage = result.get('usage') or {}
    return {'id': result.get('id') or 'msg_' + uuid.uuid4().hex, 'type': 'message',
            'role': 'assistant', 'model': model, 'content': blocks,
            'stop_reason': stop_reason(choice.get('finish_reason')), 'stop_sequence': None,
            'usage': {'input_tokens': usage.get('prompt_tokens', 0),
                      'output_tokens': usage.get('completion_tokens', 0)}}


def sse_objects(response):
    data = []
    for raw in response:
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            if data:
                value = '\n'.join(data)
                data = []
                if value == '[DONE]':
                    return
                yield json.loads(value)
        elif line.startswith('data:'):
            data.append(line[5:].lstrip(' '))
    if data:
        value = '\n'.join(data)
        if value != '[DONE]':
            yield json.loads(value)


def message_events(chunks, model):
    """Stream text/reasoning; assemble parallel function arguments by index."""
    yield {'type': 'message_start', 'message': {
        'id': 'msg_' + uuid.uuid4().hex, 'type': 'message', 'role': 'assistant',
        'model': model, 'content': [], 'stop_reason': None, 'stop_sequence': None,
        'usage': {'input_tokens': 0, 'output_tokens': 0}}}
    index, current, finish, usage, calls = -1, None, None, {}, {}
    for chunk in chunks:
        if chunk.get('error'):
            raise ProtocolError('Upstream reported a streaming error')
        usage = chunk.get('usage') or usage
        for choice in chunk.get('choices', []):
            if choice.get('index', 0) != 0:
                continue
            finish = choice.get('finish_reason') or finish
            delta = choice.get('delta') or {}
            for kind, text in [('thinking', delta.get('reasoning_content') or delta.get('reasoning')),
                               ('text', delta.get('content'))]:
                if not text:
                    continue
                if current != kind:
                    if current:
                        yield {'type': 'content_block_stop', 'index': index}
                    index += 1
                    current = kind
                    block = {'type': kind, 'thinking' if kind == 'thinking' else 'text': ''}
                    if kind == 'thinking':
                        block['signature'] = ''
                    yield {'type': 'content_block_start', 'index': index, 'content_block': block}
                yield {'type': 'content_block_delta', 'index': index, 'delta': {
                    'type': 'thinking_delta' if kind == 'thinking' else 'text_delta',
                    'thinking' if kind == 'thinking' else 'text': text}}
            for piece in delta.get('tool_calls', []):
                call = calls.setdefault(piece['index'], {'id': '', 'function': {'name': '', 'arguments': ''}})
                call['id'] += piece.get('id') or ''
                for key in ['name', 'arguments']:
                    call['function'][key] += (piece.get('function') or {}).get(key) or ''
    reason = stop_reason(finish)  # Never turn a disconnected stream into success.
    if current:
        yield {'type': 'content_block_stop', 'index': index}
    for key in sorted(calls):
        block = tool_block(calls[key])
        index += 1
        yield {'type': 'content_block_start', 'index': index, 'content_block': {
            'type': 'tool_use', 'id': block['id'], 'name': block['name'], 'input': {}}}
        yield {'type': 'content_block_delta', 'index': index, 'delta': {
            'type': 'input_json_delta', 'partial_json': calls[key]['function']['arguments']}}
        yield {'type': 'content_block_stop', 'index': index}
    yield {'type': 'message_delta', 'delta': {'stop_reason': reason, 'stop_sequence': None},
           'usage': {'input_tokens': usage.get('prompt_tokens', 0),
                     'output_tokens': usage.get('completion_tokens', 0)}}
    yield {'type': 'message_stop'}


def send_json(handler, status, body):
    data = json.dumps(body, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def forward(handler, base_url, api_key, model, extra_body=None, forward_reasoning=False, timeout=3600):
    """Handle one local request without echoing upstream bodies or credentials."""
    streaming = False
    try:
        route = urllib.parse.urlsplit(handler.path).path.rstrip('/')
        if handler.command != 'POST' or route not in {'/v1/messages', '/messages'}:
            send_json(handler, 501, {'type': 'error', 'error': {
                'type': 'not_supported_error', 'message': 'Only messages is supported; token counting is not estimated.'}})
            return False
        body = json.loads(handler.rfile.read(int(handler.headers.get('Content-Length', '0'))))
        payload = to_openai(body, model, extra_body, forward_reasoning)
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        request = urllib.request.Request(completion_url(base_url),
            data=json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if payload['stream']:
                if 'text/event-stream' not in response.headers.get('Content-Type', ''):
                    raise ProtocolError('Expected an OpenAI SSE stream')
                handler.send_response(200)
                handler.send_header('Content-Type', 'text/event-stream')
                handler.send_header('Cache-Control', 'no-cache')
                handler.send_header('Connection', 'close')
                handler.end_headers()
                streaming = True
                for event in message_events(sse_objects(response), model):
                    data = 'event: ' + event['type'] + '\ndata: ' + json.dumps(event, ensure_ascii=False) + '\n\n'
                    handler.wfile.write(data.encode())
                    handler.wfile.flush()
            else:
                send_json(handler, 200, to_message(json.load(response), model))
        return True
    except (OSError, http.client.HTTPException, ValueError, KeyError, IndexError, TypeError) as error:
        status = error.code if isinstance(error, urllib.error.HTTPError) and 400 <= error.code <= 599 else 502
        message = str(error) if isinstance(error, ProtocolError) else 'OpenAI upstream request failed (' + type(error).__name__ + ')'
        result = {'type': 'error', 'error': {'type': 'api_error', 'message': message}}
        try:
            if streaming:
                handler.wfile.write(('event: error\ndata: ' + json.dumps(result) + '\n\n').encode())
                handler.wfile.flush()
            else:
                send_json(handler, status, result)
        except OSError:
            pass
        return False


def make_server(base_url, api_key, model, port=0, extra_body=None, forward_reasoning=False):
    completion_url(base_url)
    if not model:
        raise ProtocolError('Configure OPENAI_MODEL')
    to_openai({'messages': []}, model, extra_body)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            forward(self, base_url, api_key, model, extra_body, forward_reasoning)

        def do_GET(self):
            if self.path == '/health':
                send_json(self, 200, {'protocol': 'openai_chat_completions', 'configured': True,
                    'model': model, 'upstream_probed': False,
                    'note': 'Configuration only; this endpoint does not qualify upstream availability.'})
            else:
                send_json(self, 404, {'error': {'message': 'Unknown endpoint'}})

    return http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL'), required=not os.environ.get('OPENAI_BASE_URL'))
    parser.add_argument('--model', default=os.environ.get('OPENAI_MODEL'), required=not os.environ.get('OPENAI_MODEL'))
    parser.add_argument('--api-key-env', default='OPENAI_API_KEY')
    parser.add_argument('--port', type=int, default=8092)
    parser.add_argument('--extra-body', default='{}')
    parser.add_argument('--forward-reasoning', action='store_true')
    args = parser.parse_args()
    completion_url(args.base_url)
    extra = json.loads(args.extra_body)

    server = make_server(args.base_url, os.environ.get(args.api_key_env, ''), args.model,
                         args.port, extra, args.forward_reasoning)
    print(json.dumps({'listening': '127.0.0.1', 'port': server.server_port,
                      'upstream_protocol': 'openai_chat_completions',
                      'credentials_logged': False}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
