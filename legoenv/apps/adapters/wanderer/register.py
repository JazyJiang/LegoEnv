"""Source-bound wanderer adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wanderer';NEW_SERVER={APP:'wanderer_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'ActivityPubActor', 'Category', 'Subcategory']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses real User1 and ActivityPubActor2 scaffold. get_list(id) reads List.description policy. create_list(name,description,public) sets original local actor author via source lookup; update_list(id,name,description), delete_list(id) change local rows. Source direct reads ignore scope; list_lists wrongly compares actor author to user id and omits own private lists. No hiking route parsing, federation or external activity.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='wanderer';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('get_list', {'id': 201}), ('list_lists', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'List',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update list202 description to Reviewed and approved. and name to Reviewed. Create Approved list. Keep Reference unchanged.', 'author': 2, 'public': False}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'author': 2, 'public': False}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference list.', 'author': 2, 'public': False}])
    steps=[('__APP__', 'update_list', {'id': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'update_list', {'id': 202, 'name': 'Reviewed'}), ('__APP__', 'create_list', {'name': 'Approved', 'description': 'Approved list.', 'public': False})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'List'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'List'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'List'),AND(F('name','eq','Approved'),F('author','eq',2)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'List'),AND(F('id','eq',203),F('description','eq','Retain reference list.')))),True))
    return steps,preds
