'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound svix_webhooks adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='svix_webhooks';NEW_SERVER={APP:'svix_webhooks_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['']]}
NEW_NOTES={APP:'{p}__ Source has no authentication interface. eventtype_get(event_type_name=policy) reads description. Native public eventtype_create(name,description), eventtype_patch(event_type_name,description,deprecated), eventtype_delete(event_type_name,expunge) edit local metadata. Delete always hard deletes even expunge=false. No auth/JWT or webhook delivery invented.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='svix_webhooks';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('eventtype_get', {'event_type_name': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'EventType',[{'id': 201, 'org_id': 1, 'name': 'policy', 'description': 'Policy: update review event description to Reviewed and approved. and deprecated true. Create approved event type. Keep Reference unchanged.', 'deleted': False, 'deprecated': False}, {'id': 202, 'org_id': 1, 'name': 'review', 'description': 'Pending review.', 'deleted': False, 'deprecated': False}, {'id': 203, 'org_id': 1, 'name': 'reference', 'description': 'Retain reference event.', 'deleted': False, 'deprecated': False}])
    steps=[('__APP__', 'eventtype_patch', {'event_type_name': 'review', 'description': 'Reviewed and approved.', 'deprecated': True}), ('__APP__', 'eventtype_create', {'name': 'approved', 'description': 'Approved event.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'EventType'),AND(F('name','eq','review'),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'EventType'),AND(F('name','eq','review'),F('deprecated','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'EventType'),AND(F('name','eq','approved'),F('description','eq','Approved event.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'EventType'),AND(F('name','eq','reference'),F('description','eq','Retain reference event.')))),True))
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
