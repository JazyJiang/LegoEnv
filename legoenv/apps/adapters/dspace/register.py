'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound dspace adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='dspace';NEW_SERVER={APP:'dspace_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['EPerson', 'Item', 'Collection', 'Community', 'DSpaceObject', 'MetadataSchema', 'MetadataField', 'MetadataValue']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original EPerson. fetch_item(uuid) and search_items(query) expose item flags/identifiers, no MetadataValue text join. No native readable policy carrier, complete admission blocked. Independent group_create(name), group_setname(uuid,name), group_delete(uuid) mutate metadata. Source can_log_in check is not admin membership; OR permits permanent group edits. No repository/binary/DOI/email effects.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='dspace';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('fetch_item', {'uuid': 40}), ('search_items', {'query': ''})]:
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
    records(W,'Group',[{'id': 201, 'uuid': 201, 'name': 'Operations', 'permanent': True}, {'id': 202, 'uuid': 202, 'name': 'Review', 'permanent': False}, {'id': 203, 'uuid': 203, 'name': 'Reference', 'permanent': False}])
    steps=[('__APP__', 'group_setname', {'uuid': 202, 'name': 'Reviewed group'}), ('__APP__', 'group_create', {'name': 'Approved group'}), ('__APP__', 'group_setname', {'uuid': 201, 'name': 'Reviewed operations'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Group'),AND(F('uuid','eq',202),F('name','eq','Reviewed group')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Group'),F('name','eq','Approved group'))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Group'),AND(F('uuid','eq',201),F('name','eq','Reviewed operations')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Group'),AND(F('uuid','eq',203),F('name','eq','Reference')))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
