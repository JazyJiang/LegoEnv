#!/usr/bin/env python3
"""Portable release entrypoints. The demo is synthetic and is not research data."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def build_demo(a):
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    entity='demo__Record';tool='demo__record_update'
    spec={'env_id':'release_demo','now':'2026-01-01T00:00:00','about':'A synthetic two-record workspace used only for an offline installation check.',
          'entities':[{'name':entity,'columns':[{'name':'id','type':'int','pk':True},{'name':'status','type':'text'}]}],
          'tools':[{'tool':tool,'family':'update.field_set','entity':entity,'input_schema':{'id':{'type':'int'},'status':{'type':'text'}},'exec_spec':{'lookup_by':{'id':{'$arg':'id'}},'set':{'status':{'$arg':'status'}}}}],
          'seed_state':{entity:[{'id':1,'status':'pending'},{'id':2,'status':'held'}]}}
    task={'env_id':'release_demo','goal_nl':"Set record 1's status to reviewed. Leave record 2's status unchanged.",
          'verifier':{'op':'and','clauses':[{'op':'field_eq','entity':entity,'where':{'id':1},'col':'status','value':'reviewed'},{'op':'field_eq','entity':entity,'where':{'id':2},'col':'status','value':'held'}]},
          'witness':[{'tool':tool,'args':{'id':1,'status':'reviewed'}}]}
    save(out/'demo.spec.json',spec);save(out/'demo.task.json',task)
    (out/'packs.tsv').write_text(f"release_demo\t{out/'demo.task.json'}\t{out/'demo.spec.json'}\t-\n")
    print(json.dumps({'fixture_only':True,'pack_list':str(out/'packs.tsv')}))


def verify(a):
    os.environ.setdefault('ENVLIB_COLUMN_DEFAULTS','1')
    sys.path.insert(0,str(ROOT/'runtime'))
    import runtime
    spec=json.loads(Path(a.spec).read_text());task=json.loads(Path(a.task).read_text())
    env=runtime.Env(spec);v=runtime.Verifier()
    initial=v.eval(task['verifier'],env.state);steps=[]
    for step in task['witness']:
        result=env.call(step['tool'],step.get('args',{}));steps.append({'tool':step['tool'],'ok':result.get('ok') is True})
        if not steps[-1]['ok']:raise RuntimeError(f"Witness call failed: {step['tool']}")
    final=v.eval(task['verifier'],env.state);reset=v.eval(task['verifier'],runtime.Env(spec).state)
    result={'seed_verifier':initial,'final_verifier':final,'reset_verifier':reset,'steps':steps,'passed':initial is False and final is True and reset is False}
    print(json.dumps(result,ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)


def sample(a):
    collector=ROOT/'tools/collect.py'
    env=os.environ.copy();env.setdefault('ENVLIB_COLUMN_DEFAULTS','1')
    if a.api_key_env and env.get(a.api_key_env):env['TEACHER_API_KEY']=env[a.api_key_env]
    command=[sys.executable,str(collector),'--packs',a.packs,'--out',a.out,'--base-url',a.base_url,'--model',a.model,'--api-key-env','TEACHER_API_KEY','--samples',str(a.samples),'--workers',str(a.workers),'--max-turns','100','--wall-cap','28800','--temperature','1.0','--top-p','0.95','--extra-body',a.extra_body]
    if a.dry_run:
        print(json.dumps({'command':command,'credentials_from_environment_only':True},ensure_ascii=False));return
    raise SystemExit(subprocess.call(command,env=env,cwd=ROOT))


def render_builder(a):
    command=[sys.executable,'-B',str(ROOT/'tools/render_builder_prompt.py'),'--skeleton',a.skeleton,'--contract',a.contract,'--out',a.out]
    if a.base_specs:command+=['--base-specs',a.base_specs]
    raise SystemExit(subprocess.call(command,cwd=ROOT))


def main():
    if sys.argv[1:2] == ['build-native']:
        raise SystemExit(subprocess.call([sys.executable, str(ROOT/'tools/build_native.py'), *sys.argv[2:]], cwd=ROOT))
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    s.add_parser('build-native',help='Build from a skeleton with the isolated native stack; use build-native --help for options.')
    q=s.add_parser('build-demo');q.add_argument('--out',required=True);q.set_defaults(fn=build_demo)
    q=s.add_parser('verify');q.add_argument('--task',required=True);q.add_argument('--spec',required=True);q.set_defaults(fn=verify)
    q=s.add_parser('sample');q.add_argument('--packs',required=True);q.add_argument('--out',required=True);q.add_argument('--base-url',default=os.environ.get('OPENAI_BASE_URL'),required=not os.environ.get('OPENAI_BASE_URL'));q.add_argument('--model',default=os.environ.get('OPENAI_MODEL'),required=not os.environ.get('OPENAI_MODEL'));q.add_argument('--api-key-env',default='OPENAI_API_KEY');q.add_argument('--extra-body',default='{}');q.add_argument('--samples',type=int,default=8);q.add_argument('--workers',type=int,default=4);q.add_argument('--dry-run',action='store_true');q.set_defaults(fn=sample)
    q=s.add_parser('render-builder');q.add_argument('--skeleton',required=True);q.add_argument('--contract',required=True);q.add_argument('--base-specs');q.add_argument('--out',required=True);q.set_defaults(fn=render_builder)
    args=p.parse_args();args.fn(args)


if __name__=='__main__':main()
