#!/usr/bin/env python3
NAMESPACE = '#!/usr/bin/env bash\nset -euo pipefail\nroot=$1; actor=$2; pyroot=$3; datapython=$4; library=$5; dp=$6; cc=$7; mode=$8; relay=$9; datadeps=${10}\nmount --make-rprivate /\nip link set lo up\nmount -t tmpfs -o size=128m,nosuid tmpfs "$root"\nmkdir -p "$root"/{usr,bin,lib,lib64,etc,dev,proc,tmp,builder,opt/python,opt/data_python,opt/data_deps,opt/cc,home/actor}\nfor dir in usr bin lib lib64; do\n if test -e /"$dir"; then mount --bind /"$dir" "$root/$dir"; mount -o remount,bind,ro "$root/$dir"; fi\ndone\nfor file in ld.so.cache hosts resolv.conf nsswitch.conf; do\n if test -f /etc/"$file"; then touch "$root/etc/$file"; mount --bind /etc/"$file" "$root/etc/$file"; mount -o remount,bind,ro "$root/etc/$file"; fi\ndone\nfor file in null zero random urandom; do touch "$root/dev/$file"; mount --bind /dev/"$file" "$root/dev/$file"; done\nmount -t proc proc "$root/proc"\nmount --bind "$pyroot" "$root/opt/python"; mount -o remount,bind,ro "$root/opt/python"\nmount --bind "$datapython" "$root/opt/data_python"; mount -o remount,bind,ro "$root/opt/data_python"\nmount --bind "$datadeps" "$root/opt/data_deps"; mount -o remount,bind,ro "$root/opt/data_deps"\ntouch "$root/opt/cc/claude.exe"; mount --bind "$cc" "$root/opt/cc/claude.exe"; mount -o remount,bind,ro "$root/opt/cc/claude.exe"\nmount --bind "$actor/work" "$root/builder"\nif test "$mode" = agent; then\n touch "$root/builder/provider.sock"\n mount --bind "$relay" "$root/builder/provider.sock"\nfi\nfor pair in "LegoEnv:$library" "datapool:$dp/datapool" "datapool_ext:$dp/datapool_ext" "auxiliary_inputs:$dp/auxiliary_inputs"; do\n name=${pair%%:*}; src=${pair#*:}; if ! test -d "$src"; then continue; fi\n mkdir -p "$root/builder/$name"; mount --bind "$src" "$root/builder/$name"; mount -o remount,bind,ro "$root/builder/$name"\ndone\nfor dir in base_specs newspecs newspecs2 newspecs3 batches clean_quality_review clean_leave_closeout; do\n dest="$root/builder/smoke/pack/$dir"; mount --bind "$dest" "$dest"; mount -o remount,bind,ro "$dest"\ndone\nfor file in pack_dpsk/BUILDER.md pack/packlib.py pack/accept.py pack/fill_witness.py pack/emit_task.py pack/argnorm.py pack/DATA_INVENTORY.md pack_dpsk/dklib.py; do\n dest="$root/builder/smoke/$file"; mount --bind "$dest" "$dest"; mount -o remount,bind,ro "$dest"\ndone\nfor dir in .claude pack_dpsk/contract inputs; do\n dest="$root/builder/smoke/$dir"; mount --bind "$dest" "$dest"; mount -o remount,bind,ro "$dest"\ndone\ncd "$root"\nmain_pythonpath=/builder/smoke/pack:/builder/smoke/pack/batches:/builder/smoke/pack_dpsk\nif test "$pyroot" = "$datapython"; then main_pythonpath=/opt/data_deps:$main_pythonpath; fi\nexec chroot "$root" /usr/bin/env -i HOME=/home/actor TMPDIR=/tmp \\\n PATH=/builder/bin:/usr/bin:/bin:/opt/python/bin PYTHONHOME=/opt/python \\\n PYTHONPATH="$main_pythonpath" \\\n PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANG=C.UTF-8 \\\n ANTHROPIC_BASE_URL=http://127.0.0.1:8092 ANTHROPIC_API_KEY=local-relay-placeholder \\\n ANTHROPIC_AUTH_TOKEN=local-relay-placeholder CLAUDE_CONFIG_DIR=/home/actor/.claude \\\n CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \\\n DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1 DISABLE_AUTOUPDATER=1 IS_SANDBOX=1 API_TIMEOUT_MS=3000000 \\\n /usr/bin/setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \\\n /opt/python/bin/python3.12 /builder/entry.py "$mode"\n'
ENTRY = 'import json,os,pathlib,socket,subprocess,sys,threading,socketserver,select\nos.chdir(\'/builder/smoke\')\nroot=pathlib.Path(\'/builder\')\ndef pump(left,right):\n try:\n  while True:\n   readable,_,_=select.select([left,right],[],[],300)\n   if not readable:return\n   for src in readable:\n    data=src.recv(65536)\n    if not data:return\n    (right if src is left else left).sendall(data)\n finally:\n  left.close();right.close()\nclass Tunnel(socketserver.BaseRequestHandler):\n def handle(self):\n  remote=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)\n  remote.connect(\'/builder/provider.sock\');pump(self.request,remote)\nclass Server(socketserver.ThreadingTCPServer):\n allow_reuse_address=True;daemon_threads=True\nchecks={\n \'host_mount_tree_absent\':not pathlib.Path(\'/mnt\').exists(),\n \'host_proc_mounts_absent\':not pathlib.Path(\'/proc/1/root/mnt\').exists(),\n \'controller_provenance_absent\':not (root/\'provenance\').exists(),\n \'caps_dropped\':\'CapEff:\\t0000000000000000\' in pathlib.Path(\'/proc/self/status\').read_text(),\n}\ntry:\n with (root/\'smoke/pack/packlib.py\').open(\'a\') as f:f.write(\'SHOULD_BE_DENIED\')\n checks[\'library_write_denied\']=False\nexcept OSError:checks[\'library_write_denied\']=True\ntry:\n with socket.create_connection((\'198.51.100.1\',443),timeout=1):pass\n checks[\'external_network_denied\']=False\nexcept OSError:checks[\'external_network_denied\']=True\nchecks[\'passed\']=all(checks.values())\n(root/\'isolation.json\').write_text(json.dumps(checks,indent=2)+\'\\n\')\nif not checks[\'passed\']:raise SystemExit(\'Builder isolation failed\')\nif sys.argv[1]==\'cpu-probe\':\n import packlib as p\n from dklib import sim_gold,check\n from argnorm import normalize\n import accept\n from newspecs.register import *\n from newspecs3.planka.register import *\n from newspecs2.register import *\n checked_bases=[]\n for app in sorted(p.SERVER):\n  if app==\'planka\':continue\n  base_world=p.World([app],persona=(\'release@demo.example\',\'Release operator\'),now=\'2026-10-21T08:00:00\')\n  base_spec=base_world.merge()\n  assert all(e[\'name\'].startswith(p.PFX[app]+\'__\') for e in base_spec[\'entities\'])\n  assert all(t[\'tool\'].startswith(p.PFX[app]+\'__\') for t in base_spec[\'tools\'])\n  checked_bases.append(app)\n assert len(checked_bases)==19,checked_bases\n W=p.World([\'budibase\',\'stalwart\',\'planka\'],persona=(\'ops@probe.example\',\'Probe operator\'),now=\'2026-10-20T08:00:00\')\n spec=W.merge();rep,bad=W.obs_report()\n assert not bad,bad\n data_probe=subprocess.run([\'python3\',\'-c\',\'import pyarrow,openpyxl,yaml;print("DATA_PYTHON_IMPORTS_PASS")\'],capture_output=True,text=True,timeout=40)\n result={\'base_namespaces_checked\':checked_bases,\'imports_passed\':True,\'admission_module_imported\':True,\'argument_normalizer_imported\':True,\'apps\':W.apps,\'tools\':len(spec[\'tools\']),\'observation_bad\':bad,\n  \'data_python_returncode\':data_probe.returncode,\'data_python_stdout\':data_probe.stdout,\'data_python_stderr\':data_probe.stderr[-1000:],\n  \'formal_admission_result\':False,\'model_requests\':0}\n (root/\'cpu_probe.json\').write_text(json.dumps(result,indent=2)+\'\\n\')\n assert data_probe.returncode==0,result\n print(json.dumps(result));raise SystemExit(0)\nserver=Server((\'127.0.0.1\',8092),Tunnel)\nthreading.Thread(target=server.serve_forever,daemon=True).start()\nargs=[\'/opt/cc/claude.exe\',\'-p\',\'Read inputs/BRIEF.md and do exactly what it says.\',\n \'--model\',json.loads((root/\'limits.json\').read_text())[\'cc_model\'],\'--max-turns\',str(json.loads((root/\'limits.json\').read_text())[\'max_turns\']),\n \'--dangerously-skip-permissions\',\'--tools\',\'Bash,Read,Write,Edit,Glob,Grep\',\n \'--allowedTools\',\'Bash\',\'Read\',\'Write\',\'Edit\',\'Glob\',\'Grep\',\'--strict-mcp-config\',\'--mcp-config\',\'{"mcpServers":{}}\',\n \'--setting-sources\',\'\',\'--no-session-persistence\',\'--output-format\',\'json\']\nresult=subprocess.run(args)\n(root/\'agent_check_reports.json\').write_text(json.dumps([\n json.loads(p.read_text()) for p in sorted((root/\'smoke/pack_dpsk/results\').glob(\'*.json\'))\n],indent=2)+\'\\n\')\nindependent=[]\nreported={r.get(\'tid\') for r in json.loads((root/\'agent_check_reports.json\').read_text()) if isinstance(r.get(\'tid\'),str)}\nfor package in sorted(root/\'smoke/pack\'/tid for tid in reported if tid and all(c.islower() or c.isdigit() or c==\'_\' for c in tid)):\n if not (package/\'05_verifier/contract.json\').is_file():continue\n if not all(c.islower() or c.isdigit() or c==\'_\' for c in package.name):continue\n program=\'from dklib import check;raise SystemExit(0 if check(\'+repr(package.name)+\',\'+repr(json.loads((root/\'limits.json\').read_text()).get(\'skeleton_id\'))+\') else 1)\'\n try:\n  check=subprocess.run([\'python3.12\',\'-c\',program],cwd=root/\'smoke/pack\',capture_output=True,text=True,timeout=3600)\n  (package/\'independent_check.stdout\').write_text(check.stdout)\n  (package/\'independent_check.stderr\').write_text(check.stderr)\n  independent.append({\'tid\':package.name,\'returncode\':check.returncode})\n except subprocess.TimeoutExpired:\n  independent.append({\'tid\':package.name,\'returncode\':\'timeout\'})\n(root/\'independent_checks.json\').write_text(json.dumps(independent,indent=2)+\'\\n\')\nraise SystemExit(result.returncode)\n'
"""Portable Linux native builder; namespace constants are supplied by assembly."""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.parse
import openai_bridge
import builder_workspace

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def pump(left,right):
    try:
        while True:
            ready,_,_=select.select([left,right],[],[],3600)
            if not ready:return
            for src in ready:
                body=src.recv(65536)
                if not body:return
                (right if src is left else left).sendall(body)
    finally:left.close();right.close()


def main():
    p=argparse.ArgumentParser(description='Build one native environment in an isolated Linux workspace.')
    p.add_argument('--stack',type=Path,help='Pre-staged workspace (smoke/ and LegoEnv/); by default it is staged from this repository.')
    p.add_argument('--data',type=Path,required=True,help='Root containing datapool/ and optionally datapool_ext/.')
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--skeleton',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--python-root',type=Path,required=True,help='Complete Python3.12 prefix, including its standard library.')
    p.add_argument('--data-python-root',type=Path)
    p.add_argument('--data-deps',type=Path,required=True)
    p.add_argument('--claude',type=Path,required=True,help='An installed Claude Code executable; not bundled.')
    p.add_argument('--provider-base-url',default=os.environ.get('OPENAI_BASE_URL'),required=not os.environ.get('OPENAI_BASE_URL'),help='OpenAI-compatible API base, normally ending in /v1.')
    p.add_argument('--api-key-env',default='OPENAI_API_KEY')
    p.add_argument('--model',default=os.environ.get('OPENAI_MODEL'),required=not os.environ.get('OPENAI_MODEL'),help='Actual upstream model name.')
    p.add_argument('--provider-extra-body',default='{}',help='Optional provider extensions as a JSON object; no implicit thinking settings.')
    p.add_argument('--forward-reasoning',action='store_true',help='For compatible self-hosted models, forward earlier thinking as reasoning_content.')
    p.add_argument('--max-turns',type=int,default=160)
    p.add_argument('--wall-seconds',type=int,default=18000)
    p.add_argument('--namespace-mode',choices=['user','root'],default='user')
    p.add_argument('--cpu-probe',action='store_true',help='Check real namespace/dependencies without making a model request.')
    a=p.parse_args()
    if a.namespace_mode=='root' and os.geteuid()!=0:p.error('root mode requires an already privileged executor')
    if a.max_turns<=0 or a.wall_seconds<=0:p.error('Budgets must be positive')
    try:
        openai_bridge.completion_url(a.provider_base_url)
        provider_extra=json.loads(a.provider_extra_body)
        openai_bridge.to_openai({'messages':[]},a.model,provider_extra)
    except (ValueError,TypeError) as error:
        p.error(str(error))
    stack=a.stack.resolve() if a.stack else None;data=a.data.resolve();out=a.out.resolve()
    sources=[stack/'smoke/pack/packlib.py',stack/'LegoEnv/runtime/runtime.py'] if stack else [ROOT/'builder/packlib.py',ROOT/'builder/legacy_runtime/runtime.py']
    for path in [*sources,a.skeleton,a.inventory,a.claude]:
        if not path.is_file():p.error('Required local input is absent: '+str(path))
    version=subprocess.check_output([str(a.claude.resolve()),'--version'],text=True,timeout=30,
        env={**os.environ,'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}).strip()
    if version.split()[0]!='2.1.186':
        p.error('Claude Code 2.1.186 is required; use the version-locked downloader in bridge/')
    if not (data/'datapool').is_dir():p.error('The supplied data root needs a datapool directory')
    for path in [a.python_root,a.data_python_root or a.python_root,a.data_deps]:
        if not path.is_dir():p.error('Python/dependency prefix does not exist')
    skeleton=json.loads(a.skeleton.read_text());sid=skeleton.get('skeleton_id')
    if not isinstance(sid,str) or not sid or not isinstance(skeleton.get('apps'),list):p.error('Supply a skeleton with skeleton_id and apps')
    out.mkdir(parents=True,exist_ok=False);actor=out/'work';actor.mkdir()
    if stack is None:stack=builder_workspace.stage(ROOT,out/'stack')
    shutil.copytree(stack/'smoke',actor/'smoke',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ['LegoEnv','datapool','datapool_ext','bin']:(actor/name).mkdir(exist_ok=True)
    (actor/'smoke/inputs').mkdir(exist_ok=True)
    shutil.copyfile(a.inventory,actor/'smoke/pack/DATA_INVENTORY.md')
    clean={k:v for k,v in skeleton.items() if not k.startswith('_')}
    brief=(actor/'smoke/pack_dpsk/BUILDER.md').read_text().replace('{SK}',sid).replace('{SKELETON_JSON}',json.dumps(clean,ensure_ascii=False,indent=1))
    (actor/'smoke/inputs/BRIEF.md').write_text(brief)
    save(actor/'smoke/inputs/skeleton.json',clean)
    save(actor/'limits.json',{'max_turns':a.max_turns,'skeleton_id':sid,'cc_model':a.model})
    (actor/'entry.py').write_text(ENTRY)
    (actor/'bin/python3').write_text('#!/bin/bash\nunset PYTHONHOME\nexport PYTHONPATH=/opt/data_deps${PYTHONPATH:+:$PYTHONPATH}\nexec /opt/data_python/bin/python3 "$@"\n')
    (actor/'bin/python3').chmod(0o755);(actor/'bin/python3.12').symlink_to('/opt/python/bin/python3.12')
    (out/'namespace.sh').write_text(NAMESPACE);(out/'root').mkdir()
    save(out/'INPUTS.json',{'registered_at':time.time(),'skeleton_id':sid,'skeleton_sha256':digest(a.skeleton),
        'inventory_sha256':digest(a.inventory),'builder_prompt_sha256':hashlib.sha256(brief.encode()).hexdigest(),
        'runtime_sha256':digest(stack/'LegoEnv/runtime/runtime.py'),'cc_executable_sha256':digest(a.claude),
        'max_turns':a.max_turns,'wall_seconds':a.wall_seconds,'attempts':1,'credentials_in_agent':False,
        'upstream_protocol':'openai_chat_completions','forward_reasoning':a.forward_reasoning})
    api_key=os.environ.get(a.api_key_env,'')
    request_counts={'requests':0,'responses':0,'transport_errors':0}
    mutex=threading.Lock()
    class Proxy(http.server.BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        def log_message(self,*unused):pass
        def do_POST(self):self.forward()
        def do_GET(self):self.forward()
        def forward(self):
            with mutex:request_counts['requests']+=1
            passed=openai_bridge.forward(self,a.provider_base_url,api_key,a.model,
                                         provider_extra,a.forward_reasoning)
            with mutex:request_counts['responses' if passed else 'transport_errors']+=1
    proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy)
    threading.Thread(target=proxy.serve_forever,daemon=True).start()
    class Tunnel(socketserver.BaseRequestHandler):
        def handle(self):pump(self.request,socket.create_connection(('127.0.0.1',proxy.server_port),timeout=3600))
    class Unix(socketserver.ThreadingUnixStreamServer):daemon_threads=True
    child=None;relay=None
    def cancelled(*unused):raise InterruptedError('Build interrupted')
    signal.signal(signal.SIGTERM,cancelled)
    started=time.time()
    try:
        with tempfile.TemporaryDirectory(prefix='native-builder-relay-',dir='/tmp') as temp:
            address=str(Path(temp)/'provider.sock');relay=Unix(address,Tunnel)
            threading.Thread(target=relay.serve_forever,daemon=True).start()
            flags=['--mount','--pid','--net','--fork']
            if a.namespace_mode=='user':flags=['--user','--map-root-user',*flags]
            argv=['unshare',*flags,'bash',str(out/'namespace.sh'),str(out/'root'),str(out),str(a.python_root.resolve()),
                str((a.data_python_root or a.python_root).resolve()),str(stack/'LegoEnv'),str(data),str(a.claude.resolve()),
                'cpu-probe' if a.cpu_probe else 'agent',address,str(a.data_deps.resolve())]
            env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['TOKEN','SECRET','API_KEY','PROXY','PYTHONHOME','PYTHONPATH'])}
            env.pop(a.api_key_env,None)
            with (out/'stdout').open('w') as stdout,(out/'stderr').open('w') as stderr:
                child=subprocess.Popen(argv,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
                try:rc=child.wait(timeout=a.wall_seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL);child.wait();rc='timeout'
            if a.cpu_probe:
                isolation=json.loads((actor/'isolation.json').read_text())
                probe=json.loads((actor/'cpu_probe.json').read_text()) if (actor/'cpu_probe.json').exists() else None
                passed=rc==0 and isolation['passed'] and bool(probe and probe['data_python_returncode']==0)
                save(out/'RESULT.json',{'mode':'cpu-probe','returncode':rc,'passed':passed,
                    'isolation':isolation,'dependency_probe':probe,'provider_counts':request_counts,
                    'native_admission_claimed':False,'model_requests':0})
                assert passed and request_counts['requests']==0
                print(json.dumps({'CPU_isolation_dependencies_passed':True,'model_requests':0}));return
            checks_path=actor/'independent_checks.json'
            checks=json.loads(checks_path.read_text()) if checks_path.exists() else []
            admitted=[]
            reports_path=actor/'agent_check_reports.json'
            reports=json.loads(reports_path.read_text()) if reports_path.exists() else []
            passed={x['tid'] for x in checks if x['returncode']==0}
            for row in reports:
                tid=row.get('tid')
                if tid not in passed or not all(row.get(k) for k in ['pass','accept_strict','finish']):continue
                if row.get('skeleton_id')!=sid:continue
                emit=actor/'smoke/pack'/tid/'emit';tp=emit/(tid+'.task.json');sp=emit/(tid+'.spec.json')
                if tp.is_file() and sp.is_file():admitted.append((tid,tp,sp))
            (out/'packs.tsv').write_text(''.join('release_demo\t'+str(tp)+'\t'+str(sp)+'\t-\n' for _,tp,sp in admitted))
            isolation=json.loads((actor/'isolation.json').read_text()) if (actor/'isolation.json').exists() else None
            result={'started_at':started,'elapsed_seconds':time.time()-started,'agent_returncode':rc,
                'original_native_checks':checks,'admitted_packages':[{'tid':t,'task_sha256':digest(tp),'spec_sha256':digest(sp)} for t,tp,sp in admitted],
                'native_admitted':bool(admitted),'isolation':isolation,'provider_counts':request_counts,
                'provider_credentials_recorded':False,'automatic_quality_rerolls':0}
            save(out/'RESULT.json',result)
            print(json.dumps({'native_admitted':bool(admitted),'admitted_packages':len(admitted),'agent_returncode':rc}))
            if not admitted:raise SystemExit(1)
    finally:
        if child and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        if relay:relay.shutdown();relay.server_close()
        proxy.shutdown();proxy.server_close()


if __name__=='__main__':main()
