"""Source-bound miniserve adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='miniserve';NEW_SERVER={APP:'miniserve_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['AuthAccount']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password) uses original plain AuthAccount. file_get(path) reads genuine File.content policy; file_list(path,search) applies source substring filters. file_upload(path,filename,content,size) inserts local text metadata, file_mkdir(path) inserts path row, file_delete(path) deletes. There is no update/rename tool. Original executor resolves file/directory kind constants; no real filesystem bytes.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='miniserve';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('file_get', {'path': '/docs/policy.txt'}), ('file_list', {'path': '/docs'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'File',[{'id': 201, 'path': '/docs/policy.txt', 'name': 'policy.txt', 'kind': 'file', 'content': 'Policy: upload /docs/approved.txt with Approved content. and /docs/complete.txt with Review complete. Create directory /archive. Keep Reference unchanged.', 'size': 100}, {'id': 202, 'path': '/docs/review.txt', 'name': 'review.txt', 'kind': 'file', 'content': 'Pending review.', 'size': 15}, {'id': 203, 'path': '/docs/reference.txt', 'name': 'reference.txt', 'kind': 'file', 'content': 'Retain reference file.', 'size': 22}])
    steps=[('__APP__', 'file_upload', {'path': '/docs/approved.txt', 'filename': 'approved.txt', 'content': 'Approved content.'}), ('__APP__', 'file_upload', {'path': '/docs/complete.txt', 'filename': 'complete.txt', 'content': 'Review complete.'}), ('__APP__', 'file_mkdir', {'path': '/archive'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'File'),AND(F('path','eq','/docs/approved.txt'),F('content','eq','Approved content.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'File'),AND(F('path','eq','/docs/complete.txt'),F('content','eq','Review complete.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'File'),F('path','eq','/archive'))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'File'),AND(F('path','eq','/docs/reference.txt'),F('content','eq','Retain reference file.')))),True))
    return steps,preds
