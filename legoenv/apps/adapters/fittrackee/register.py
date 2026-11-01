"""Source-bound fittrackee adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='fittrackee';NEW_SERVER={APP:'fittrackee_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'EquipmentType', 'Sport']]}
NEW_NOTES={APP:'{p}__ user_login(email,password). equipment_get(equipment_short_id=<uuid>) reads Equipment.description policy. equipment_create(label,equipment_type,description), equipment_update(equipment_short_id,label,description,is_active), equipment_delete(equipment_short_id) edit own equipment metadata. Native direct read ignores owner scope, but update/delete ownership predicates hold. No GPX workout computation, maps/telemetry or real media bytes.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='fittrackee';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('equipment_get', {'equipment_short_id': 'policy-equipment'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Equipment',[{'id': 201, 'uuid': 'policy-equipment', 'label': 'Policy', 'description': 'Policy: update review-equipment description to Reviewed and approved. and label Reviewed. Create Approved Bike equipment. Keep Reference unchanged.', 'user_id': 1, 'equipment_type_id': 1, 'is_active': True, 'visibility': 'private'}, {'id': 202, 'uuid': 'review-equipment', 'label': 'Pending', 'description': 'Pending review.', 'user_id': 1, 'equipment_type_id': 1, 'is_active': True, 'visibility': 'private'}, {'id': 203, 'uuid': 'reference-equipment', 'label': 'Reference', 'description': 'Retain reference equipment.', 'user_id': 1, 'equipment_type_id': 1, 'is_active': True, 'visibility': 'private'}])
    steps=[('__APP__', 'equipment_update', {'equipment_short_id': 'review-equipment', 'description': 'Reviewed and approved.', 'label': 'Reviewed'}), ('__APP__', 'equipment_create', {'label': 'Approved', 'equipment_type': 1, 'description': 'Approved equipment.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Equipment'),AND(F('uuid','eq','review-equipment'),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Equipment'),AND(F('uuid','eq','review-equipment'),F('label','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Equipment'),AND(F('label','eq','Approved'),F('equipment_type_id','eq',1),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Equipment'),AND(F('uuid','eq','reference-equipment'),F('description','eq','Retain reference equipment.')))),True))
    return steps,preds
