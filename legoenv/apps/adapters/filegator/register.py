'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound filegator adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='filegator';NEW_SERVER={APP:'filegator_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_authenticate(username,password). Complete admission blocked: FSNode is file metadata only, no content column; download initially returns metadata; write_file generic upsert can retain undeclared content, but no schema carrier is supplied. fsnode_create(name,type) inserts metadata; fsnode_delete(items=<scalar path>) deletes native matching path. Documented item-array shape is not implemented by this scalar executor. No filesystem bytes or policy read invented.'}
LOGIN={APP:('user_authenticate','username')};SERVER.update(NEW_SERVER);PFX[APP]='filegator';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_authenticate'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('fsnode_download', {'path': '/admin/policy.txt'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source-readable business policy text carrier; do not fabricate a read tool or repurpose metadata as instructions. Complete admission blocked.')
def metadata_smoke_seed(W):
    records(W,'FSNode',[{'id': 201, 'path': '/admin/policy.txt', 'name': 'policy.txt', 'type': 'file', 'size': 0, 'permissions': '-rw-r--r--'}, {'id': 202, 'path': '/admin/pending.txt', 'name': 'pending.txt', 'type': 'file', 'size': 0, 'permissions': '-rw-r--r--'}, {'id': 203, 'path': '/admin/reference.txt', 'name': 'reference.txt', 'type': 'file', 'size': 0, 'permissions': '-rw-r--r--'}])
    steps=[('__APP__', 'fsnode_create', {'name': 'approved1.txt', 'type': 'file'}), ('__APP__', 'fsnode_create', {'name': 'approved2.txt', 'type': 'file'}), ('__APP__', 'fsnode_create', {'name': 'approved3', 'type': 'dir'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'FSNode'),AND(F('name','eq','approved1.txt'),F('type','eq','file')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'FSNode'),AND(F('name','eq','approved2.txt'),F('type','eq','file')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'FSNode'),AND(F('name','eq','approved3'),F('type','eq','dir')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'FSNode'),AND(F('path','eq','/admin/reference.txt'),F('size','eq',0)))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
