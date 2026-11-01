#!/usr/bin/env python3
"""Exercise the pinned real CLI against loopback protocol fixtures, not a model."""
import argparse
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from server import make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', type=Path, required=True)
    args = parser.parse_args()
    received = []

    class Fixture(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append(body)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            if len(received) == 1:
                parts = [
                    {'reasoning_content': 'Check the local protocol fixture.'},
                    {'tool_calls': [{'index': 0, 'id': 'call_protocol', 'type': 'function', 'function': {
                        'name': 'Bash', 'arguments': json.dumps({'command': 'printf bridge_protocol_ok',
                            'description': 'Print a local protocol marker'})}}]}]
                finish = 'tool_calls'
            else:
                parts, finish = [{'content': 'Bridge protocol verified.'}], 'stop'
            for delta in parts:
                event = {'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}
                self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
            self.wfile.write(('data: ' + json.dumps({'choices': [
                {'index': 0, 'delta': {}, 'finish_reason': finish}]}) + '\n\ndata: [DONE]\n\n').encode())

    upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    local = make_server('http://127.0.0.1:%d/v1' % upstream.server_port, '', 'protocol-fixture')
    threading.Thread(target=local.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='legoenv-cli-contract-') as work:
            env = {k: v for k, v in os.environ.items() if not any(
                term in k.upper() for term in ['TOKEN', 'SECRET', 'API_KEY', 'PROXY', 'ANTHROPIC', 'OPENAI'])}
            env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:%d' % local.server_port,
                       ANTHROPIC_API_KEY='local-test', CLAUDE_CONFIG_DIR=work+'/config',
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', DISABLE_AUTOUPDATER='1',
                       DISABLE_TELEMETRY='1', DISABLE_ERROR_REPORTING='1',
                       HOME=work, XDG_CONFIG_HOME=work+'/xdg', API_TIMEOUT_MS='15000')
            result = subprocess.run([str(args.claude.resolve()), '-p', 'Run the protocol check.',
                '--model', 'protocol-fixture', '--tools', 'Bash', '--allowedTools', 'Bash',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--setting-sources', '',
                '--no-session-persistence', '--max-turns', '3', '--dangerously-skip-permissions'],
                cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, (result.returncode, result.stderr[-500:], result.stdout[-500:])
        assert 'Bridge protocol verified.' in result.stdout
        assert len(received) == 2, len(received)
        tools = [m for m in received[1]['messages'] if m['role'] == 'tool']
        assert any(m.get('tool_call_id') == 'call_protocol' and 'bridge_protocol_ok' in m.get('content', '') for m in tools)
        print(json.dumps({'passed': True, 'real_CLI_used': True, 'loopback_fixture_requests': 2,
                          'real_model_requests': 0, 'research_result_claimed': False,
                          'Bash_tool_executed_and_result_returned': True}))
    finally:
        local.shutdown(); local.server_close()
        upstream.shutdown(); upstream.server_close()


if __name__ == '__main__':
    main()
