"""Client for env_host.py: one child process per episode, so a crashing world never takes
down the trainer and every episode starts from a fresh seed state."""
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
from . import paths
HOST_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'env_host.py')

def default_envlib_root():
    return os.environ.get('ENVLIB_ROOT') or os.path.join(paths.rl_root(), 'envlib')

class EnvHostError(RuntimeError):
    pass

class EnvHost:

    def __init__(self, envlib_root=None, python=None, start_timeout=120.0):
        self.envlib_root = paths.resolve(envlib_root or default_envlib_root())
        if not os.path.isfile(os.path.join(self.envlib_root, 'collect_oai.py')):
            raise EnvHostError(f'no envlib tree at {self.envlib_root}')
        self.python = python or os.environ.get('ENVLIB_ENV_PYTHON') or sys.executable
        self._err = tempfile.TemporaryFile()
        env = dict(os.environ)
        env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
        env['PYTHONUNBUFFERED'] = '1'
        self.proc = subprocess.Popen([self.python, HOST_PY, self.envlib_root], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err, env=env, start_new_session=True)
        self._buf = b''
        hello = self._read(start_timeout)
        if not hello.get('ready'):
            self.close()
            raise EnvHostError(f'env host did not start: {hello}')

    def stderr_tail(self, n=2000):
        try:
            self._err.seek(0, os.SEEK_END)
            size = self._err.tell()
            self._err.seek(max(0, size - n))
            return self._err.read().decode('utf-8', 'replace')
        except Exception:
            return ''

    def _read(self, timeout):
        deadline = time.monotonic() + timeout
        fd = self.proc.stdout.fileno()
        while b'\n' not in self._buf:
            left = deadline - time.monotonic()
            if left <= 0:
                self.close()
                raise EnvHostError(f'env host timed out after {timeout:.0f}s; stderr: {self.stderr_tail()}')
            r, _, _ = select.select([fd], [], [], min(left, 5.0))
            if not r:
                if self.proc.poll() is not None:
                    raise EnvHostError(f'env host exited rc={self.proc.returncode}; stderr: {self.stderr_tail()}')
                continue
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                rc = self.proc.poll()
                raise EnvHostError(f'env host closed its pipe (rc={rc}); stderr: {self.stderr_tail()}')
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return json.loads(line)

    def request(self, op, timeout=120.0, **kw):
        if self.proc is None:
            raise EnvHostError('env host already closed')
        if self.proc.poll() is not None:
            raise EnvHostError(f'env host is not running (rc={self.proc.returncode})')
        try:
            self.proc.stdin.write((json.dumps({'op': op, **kw}, ensure_ascii=False) + '\n').encode('utf-8'))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise EnvHostError(f'env host pipe broken: {e}; stderr: {self.stderr_tail()}')
        rep = self._read(timeout)
        if not rep.get('ok'):
            raise EnvHostError(f"env host op {op} failed: {rep.get('error')}\n{rep.get('trace', '')}")
        return rep

    def reset(self, record, timeout=300.0):
        return self.request('reset', timeout=timeout, pack_set=record.get('pack_set', 'ours'), id=record['tid'], task_path=paths.resolve(record['task_path']), spec_path=paths.resolve(record['spec_path']), system_path=paths.resolve(record.get('system_path') or '-'))

    def call(self, name, arguments, timeout=120.0):
        rep = self.request('call', timeout=timeout, name=name, arguments=arguments)
        return (rep['obs'], rep['info'])

    def verify(self, timeout=300.0):
        return self.request('verify', timeout=timeout)

    def gold_next(self, i, timeout=120.0):
        return self.request('gold_next', timeout=timeout, i=i)

    def close(self):
        p = getattr(self, 'proc', None)
        if p is None:
            return
        if p.poll() is None:
            try:
                p.stdin.write(b'{"op": "close"}\n')
                p.stdin.flush()
                p.wait(timeout=2)
            except Exception:
                pass
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except Exception:
                p.kill()
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        for f in (p.stdin, p.stdout):
            try:
                f.close()
            except Exception:
                pass
        try:
            self._err.close()
        except Exception:
            pass
        self.proc = None

    def __del__(self):
        self.close()
