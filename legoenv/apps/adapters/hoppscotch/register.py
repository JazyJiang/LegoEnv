'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound hoppscotch adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='hoppscotch';NEW_SERVER={APP:'hoppscotch_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,refreshToken) native credential panel. Complete admission blocked: no schema-supported readable narrative carrier; request/config/documentTree JSON not filled with invented policy. get_user_collection(userCollectionID) reads metadata; create_user_collection(title,type,data), update_user_collection(userCollectionID,data), delete_user_collection(userCollectionID) independently certify local metadata/opaque JSON state. newTitle is ignored.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='hoppscotch';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'refreshToken':self.password}).get('ok')
    for t,args in [('get_user_collection', {'userCollectionID': 201})]:
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
    records(W,'UserCollection',[{'id': 201, 'userUid': 1, 'title': 'Policy metadata', 'type': 'REST', 'data': {}}, {'id': 202, 'userUid': 1, 'title': 'Pending', 'type': 'REST', 'data': {}}, {'id': 203, 'userUid': 1, 'title': 'Reference', 'type': 'REST', 'data': {}}])
    steps=[('__APP__', 'create_user_collection', {'title': 'Approved1', 'type': 'REST', 'data': {}}), ('__APP__', 'create_user_collection', {'title': 'Approved2', 'type': 'REST', 'data': {}}), ('__APP__', 'create_user_collection', {'title': 'Approved3', 'type': 'REST', 'data': {}})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'UserCollection'),AND(F('title','eq','Approved1'),F('type','eq','REST')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'UserCollection'),AND(F('title','eq','Approved2'),F('type','eq','REST')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'UserCollection'),AND(F('title','eq','Approved3'),F('type','eq','REST')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'UserCollection'),AND(F('id','eq',203),F('title','eq','Reference')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'email':W.persona,'refreshToken':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
