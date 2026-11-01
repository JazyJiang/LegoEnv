'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound hyrax adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='hyrax';NEW_SERVER={APP:'hyrax_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,encrypted_password) uses original User. user_search() reads directory metadata only. No source read interface for ContentBlock.value home_text, CollectionType.description or MailboxNotification.body; complete admission blocked. Independent collectiontype_create(title,machine_id,description), collectiontype_update(id,title,description), collectiontype_destroy(id) have real state probes and original admin guards. No invented resource metadata body, downloads or repository effects.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='hyrax';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('user_search', {})]:
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
    records(W,'CollectionType',[{'id': 201, 'title': 'Operations', 'machine_id': 'operations', 'description': 'Operations collection type.'}, {'id': 202, 'title': 'Review', 'machine_id': 'review', 'description': 'Pending review.'}, {'id': 203, 'title': 'Reference', 'machine_id': 'reference', 'description': 'Retain reference description.'}])
    steps=[('__APP__', 'collectiontype_update', {'id': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'collectiontype_update', {'id': 202, 'title': 'Reviewed'}), ('__APP__', 'collectiontype_create', {'title': 'Approved', 'machine_id': 'approved', 'description': 'Approved type.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'CollectionType'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'CollectionType'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'CollectionType'),AND(F('machine_id','eq','approved'),F('description','eq','Approved type.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'CollectionType'),AND(F('id','eq',203),F('description','eq','Retain reference description.')))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
