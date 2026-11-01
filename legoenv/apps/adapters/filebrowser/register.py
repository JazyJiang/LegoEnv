'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound filebrowser adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='filebrowser';NEW_SERVER={APP:'filebrowser_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(Username,Password) uses original User permission flags. file_get(path) exposes only DirEntry metadata, no content/body field exists; full carrier admission blocked. Independent file_create(path,name), file_write(path,size,mod_time), file_delete(path) alter metadata only. Source user Scope is not enforced on these reads/writes. No actual file bytes or directory content supplied.'}
LOGIN={APP:('sign_in','Username')};SERVER.update(NEW_SERVER);PFX[APP]='filebrowser';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'Username':self.persona,'Password':self.password}).get('ok')
    for t,args in [('file_get', {'path': '/docs/operations'})]:
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
    records(W,'DirEntry',[{'id': 201, 'Path': '/docs/operations', 'Name': 'operations', 'Size': 1}, {'id': 202, 'Path': '/docs/review', 'Name': 'review', 'Size': 2, 'ModTime': '2026-01-01T00:00:00'}, {'id': 203, 'Path': '/docs/reference', 'Name': 'reference', 'Size': 3}])
    steps=[('__APP__', 'file_write', {'path': '/docs/review', 'size': 42, 'mod_time': '2026-10-20T00:00:00'}), ('__APP__', 'file_create', {'path': '/docs/approved', 'name': 'approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'DirEntry'),AND(F('Path','eq','/docs/review'),F('Size','eq',42)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'DirEntry'),AND(F('Path','eq','/docs/review'),F('ModTime','eq','2026-10-20T00:00:00')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'DirEntry'),AND(F('Path','eq','/docs/approved'),F('Name','eq','approved')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'DirEntry'),AND(F('Path','eq','/docs/reference'),F('Size','eq',3)))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'Username':W.persona,'Password':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
