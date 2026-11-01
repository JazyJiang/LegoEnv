"""CPU-only protocol contracts; local HTTP fixtures never call a real model."""
import contextlib
import copy
import http.server
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

import openai_bridge as bridge


def chunk(delta=None, finish=None):
    return {'choices': [{'index': 0, 'delta': delta or {}, 'finish_reason': finish}]}


def conversation():
    return {'system': [{'type': 'text', 'text': 'Use tools.'}], 'max_tokens': 100,
            'messages': [
                {'role': 'user', 'content': 'Read the records.'},
                {'role': 'assistant', 'content': [
                    {'type': 'thinking', 'thinking': 'Inspect first.', 'signature': ''},
                    {'type': 'tool_use', 'id': 'call_a', 'name': 'read', 'input': {'id': 7}},
                    {'type': 'tool_use', 'id': 'call_b', 'name': 'read', 'input': {'id': 8}}]},
                {'role': 'user', 'content': [
                    {'type': 'tool_result', 'tool_use_id': 'call_a', 'content': 'record seven'},
                    {'type': 'tool_result', 'tool_use_id': 'call_b', 'content': 'record eight'}]}],
            'tools': [{'name': 'read', 'input_schema': {'type': 'object', 'properties': {
                'id': {'type': 'integer'}}, 'required': ['id']}}],
            'tool_choice': {'type': 'any', 'disable_parallel_tool_use': False}}


class ConversionTests(unittest.TestCase):
    def test_conversation_and_tool_result_pairing(self):
        original = conversation()
        saved = copy.deepcopy(original)
        out = bridge.to_openai(original, 'builder')
        self.assertEqual(original, saved)
        self.assertEqual([m['role'] for m in out['messages']], ['system', 'user', 'assistant', 'tool', 'tool'])
        calls = out['messages'][2]['tool_calls']
        self.assertEqual([c['id'] for c in calls], ['call_a', 'call_b'])
        self.assertEqual([m['tool_call_id'] for m in out['messages'][3:]], ['call_a', 'call_b'])
        self.assertEqual(json.loads(calls[0]['function']['arguments']), {'id': 7})
        self.assertEqual(out['tool_choice'], 'required')
        self.assertTrue(out['parallel_tool_calls'])
        self.assertNotIn('reasoning_content', out['messages'][2])

    def test_reasoning_history_is_opt_in(self):
        out = bridge.to_openai(conversation(), 'builder', forward_reasoning=True)
        self.assertEqual(out['messages'][2]['reasoning_content'], 'Inspect first.')

    def test_extensions_cannot_replace_core_request(self):
        with self.assertRaises(bridge.ProtocolError):
            bridge.to_openai(conversation(), 'builder', {'messages': []})
        out = bridge.to_openai(conversation(), 'builder', {'reasoning_effort': 'high'})
        self.assertEqual(out['reasoning_effort'], 'high')

    def test_base_url_and_embedded_credentials(self):
        self.assertEqual(bridge.completion_url('https://provider.example/v1/'), 'https://provider.example/v1/chat/completions')
        self.assertEqual(bridge.completion_url('https://provider.example/v1/chat/completions'), 'https://provider.example/v1/chat/completions')
        for url in ['https://user:secret@provider.example/v1', 'https://provider.example/v1?key=secret', 'file:///tmp/model']:
            with self.assertRaises(bridge.ProtocolError):
                bridge.completion_url(url)

    def test_parallel_fragmented_calls_and_thinking(self):
        events = list(bridge.message_events([
            chunk({'reasoning_content': 'Check first.'}), chunk({'content': 'Reading.'}),
            chunk({'tool_calls': [
                {'index': 1, 'id': 'call_b', 'function': {'name': 'read', 'arguments': '{"id":'}},
                {'index': 0, 'id': 'call_a', 'function': {'name': 'read', 'arguments': '{"id":'}}]}),
            chunk({'tool_calls': [
                {'index': 0, 'function': {'arguments': '7}'}},
                {'index': 1, 'function': {'arguments': '8}'}}]}),
            chunk(finish='tool_calls')], 'builder'))
        blocks = [e['content_block'] for e in events if e['type'] == 'content_block_start']
        self.assertEqual([b['type'] for b in blocks], ['thinking', 'text', 'tool_use', 'tool_use'])
        self.assertEqual([b['id'] for b in blocks[2:]], ['call_a', 'call_b'])
        args = [json.loads(e['delta']['partial_json']) for e in events if e.get('delta', {}).get('type') == 'input_json_delta']
        self.assertEqual(args, [{'id': 7}, {'id': 8}])
        self.assertEqual(events[-2]['delta']['stop_reason'], 'tool_use')
        self.assertEqual(events[-1]['type'], 'message_stop')

    def test_incomplete_stream_is_not_success(self):
        events = []
        with self.assertRaises(bridge.ProtocolError):
            for event in bridge.message_events([chunk({'content': 'partial'})], 'builder'):
                events.append(event)
        self.assertNotIn('message_stop', [e['type'] for e in events])

    def test_invalid_function_arguments_are_not_repaired(self):
        with self.assertRaises(bridge.ProtocolError):
            bridge.tool_block({'id': 'call_a', 'function': {'name': 'read', 'arguments': '{broken'}})

    def test_sse_comments_and_done(self):
        data = b': heartbeat\n\ndata: {"choices": []}\n\ndata: [DONE]\n\n'
        self.assertEqual(list(bridge.sse_objects(io.BytesIO(data))), [{'choices': []}])


@contextlib.contextmanager
def serving(handler):
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class HTTPTests(unittest.TestCase):
    def run_request(self, streamed=False, fail=False):
        captured = {}

        class Upstream(http.server.BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def do_POST(self):
                captured.update(path=self.path, headers=dict(self.headers),
                                body=json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if fail:
                    bridge.send_json(self, 401, {'error': {'message': 'private upstream detail'}})
                elif streamed:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.end_headers()
                    for item in [chunk({'content': 'OK'}), chunk(finish='stop')]:
                        self.wfile.write(('data: ' + json.dumps(item) + '\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
                else:
                    bridge.send_json(self, 200, {'id': 'reply', 'choices': [
                        {'message': {'content': 'OK'}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 12, 'completion_tokens': 1}})

        with serving(Upstream) as upstream:
            class Local(http.server.BaseHTTPRequestHandler):
                def log_message(self, *unused):
                    pass

                def do_POST(self):
                    bridge.forward(self, upstream + '/v1', 'local-test', 'builder')

            with serving(Local) as local:
                request = urllib.request.Request(local + '/v1/messages?beta=true', data=json.dumps({
                    'model': 'local-cli-alias', 'stream': streamed, 'max_tokens': 10,
                    'messages': [{'role': 'user', 'content': 'Test'}]}).encode(),
                    headers={'Content-Type': 'application/json', 'x-api-key': 'local-placeholder',
                             'X-Client-Private': 'must-not-forward'})
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        result = response.read().decode()
                except urllib.error.HTTPError as error:
                    result = error.read().decode()
        self.assertEqual(captured['path'], '/v1/chat/completions')
        self.assertEqual(captured['body']['model'], 'builder')
        headers = {k.lower(): v for k, v in captured['headers'].items()}
        self.assertEqual(headers['authorization'], 'Bearer local-test')
        self.assertNotIn('x-api-key', headers)
        self.assertNotIn('x-client-private', headers)
        return result

    def test_nonstream_standard_upstream(self):
        result = json.loads(self.run_request())
        self.assertEqual(result['content'], [{'type': 'text', 'text': 'OK'}])
        self.assertEqual(result['usage'], {'input_tokens': 12, 'output_tokens': 1})

    def test_stream_standard_upstream(self):
        result = self.run_request(streamed=True)
        self.assertIn('event: message_stop', result)
        self.assertIn('"text": "OK"', result)

    def test_auth_failure_does_not_echo_sensitive_body(self):
        result = self.run_request(fail=True)
        self.assertNotIn('private upstream detail', result)
        self.assertNotIn('local-test', result)
        self.assertEqual(json.loads(result)['type'], 'error')

    def test_teacher_tools_reasoning_and_reset_world(self):
        import collect
        import pipeline
        received = []
        with tempfile.TemporaryDirectory(prefix='legoenv-protocol-') as temp:
            root = Path(temp)
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.build_demo(SimpleNamespace(out=str(root/'world')))
            task_path, spec_path = root/'world/demo.task.json', root/'world/demo.spec.json'
            spec = json.loads(spec_path.read_text())
            endpoint = collect.apistyle.Catalog(spec).by_tool['demo__record_update']
            url = endpoint['url'].replace('{id}', '1')

            class Teacher(http.server.BaseHTTPRequestHandler):
                def log_message(self, *unused):
                    pass

                def do_POST(self):
                    received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                    message = {'role': 'assistant', 'content': 'Completed.', 'reasoning_content': 'Checked.'}
                    finish = 'stop'
                    if len(received) == 1:
                        message.update(content=None, tool_calls=[{'id': 'call_update', 'type': 'function',
                            'function': {'name': 'api_fetch', 'arguments': json.dumps({
                                'method': endpoint['method'], 'url': url,
                                'body': {'id': 1, 'status': 'reviewed'}})}}])
                        finish = 'tool_calls'
                    bridge.send_json(self, 200, {'choices': [{'message': message, 'finish_reason': finish}]})

            with serving(Teacher) as teacher:
                args = SimpleNamespace(out=str(root/'episodes'), model='original-teacher',
                    base_url=teacher+'/v1', extra_body='{}', temperature=1.0, top_p=.95,
                    max_turns=5, max_tokens=128, wall_cap=30, request_timeout=5,
                    api_key_env='LEGOENV_UNUSED_TEST_API_KEY')
                row = ('protocol_fixture', task_path, spec_path, None)
                result = collect.episode(args, row, 0)
                again = collect.episode(args, row, 0)
            self.assertTrue(result['verifier_pass'])
            self.assertTrue(again['skipped_existing'])
            self.assertEqual(len(received), 2)
            self.assertEqual(received[1]['messages'][2]['reasoning_content'], 'Checked.')
            self.assertEqual(received[1]['messages'][3]['tool_call_id'], 'call_update')
            self.assertNotIn('verifier', received[0])
            self.assertNotIn('witness', received[0])
            self.assertNotIn('chat_template_kwargs', received[0])
            original = collect.runtime.Env(spec)
            task = json.loads(task_path.read_text())
            self.assertFalse(collect.runtime.Verifier().eval(task['verifier'], original.state))


if __name__ == '__main__':
    unittest.main()
