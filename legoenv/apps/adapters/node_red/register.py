"""Source-bound node_red adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='node_red';NEW_SERVER={APP:'node_red_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ auth_login(username,password). library_getentry(library=local,type=functions,path=policy) reads genuine LibraryEntry.body. library_saveentry(library,type,path,body) native upsert creates/overwrites local library records. Source lookup keys only path; library/type do not scope read identity. No flow deploy/execution or code execution is performed.'}
LOGIN={APP:('auth_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='node_red';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('library_getentry', {'library': 'local', 'type': 'functions', 'path': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'LibraryEntry',[{'id': 201, 'path': 'policy', 'type': 'functions', 'body': 'Policy: save review body Reviewed and approved. with type functions. Create approved library body Approved entry. Keep Reference unchanged.'}, {'id': 202, 'path': 'review', 'type': 'flows', 'body': 'Pending review.'}, {'id': 203, 'path': 'reference', 'type': 'functions', 'body': 'Retain reference entry.'}])
    steps=[('__APP__', 'library_saveentry', {'library': 'local', 'type': 'functions', 'path': 'review', 'body': 'Reviewed and approved.'}), ('__APP__', 'library_saveentry', {'library': 'local', 'type': 'functions', 'path': 'approved', 'body': 'Approved entry.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'LibraryEntry'),AND(F('path','eq','review'),F('body','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'LibraryEntry'),AND(F('path','eq','review'),F('type','eq','functions')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'LibraryEntry'),AND(F('path','eq','approved'),F('body','eq','Approved entry.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'LibraryEntry'),AND(F('path','eq','reference'),F('body','eq','Retain reference entry.')))),True))
    return steps,preds
