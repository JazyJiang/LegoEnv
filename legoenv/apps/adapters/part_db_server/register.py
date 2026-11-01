"""Source-bound part_db_server adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='part_db_server';NEW_SERVER={APP:'part_db_server_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'Category']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password) native username maps to User.name. part_read(id=201) reads description. part_create(name,description,categoryId), part_update(id,name,description), part_delete(id) only edit local part metadata. Existing category validation retained. Source update manufacturingStatus/categoryId aliases are not implemented by field_set executor; no stock lots or physical inventory effects claimed.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='part_db_server';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('part_read', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Part',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update part202 description to Reviewed and approved. and name Reviewed. Create Approved part in category1. Keep Reference unchanged.', 'id_category': 1}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'id_category': 1}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference part.', 'id_category': 1}])
    steps=[('__APP__', 'part_update', {'id': 202, 'name': 'Reviewed', 'description': 'Reviewed and approved.'}), ('__APP__', 'part_create', {'name': 'Approved', 'description': 'Approved part.', 'categoryId': 1})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Part'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Part'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Part'),AND(F('name','eq','Approved'),F('description','eq','Approved part.'),F('id_category','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Part'),AND(F('id','eq',203),F('description','eq','Retain reference part.')))),True))
    return steps,preds
