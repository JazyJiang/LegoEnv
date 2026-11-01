"""Source-bound homebox adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='homebox';NEW_SERVER={APP:'inventory_tag_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'UserGroup']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password), source active group gid retained. tag_getall() and tag_get(id) read Tag.description policy in active group. tag_create(name,description), tag_update(id,name,description,color), tag_delete(id) operate Tag metadata. Source tag_update parent OR target guard allows target tenant bypass with an in-group parentId; not complete isolation. Only group metadata records certified; no inventory file bytes/export/notifier/network effects.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='homebox';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('tag_getall', {}), ('tag_get', {'id': 301})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Group',[{'id':2,'name':'Other synthetic group','currency':'usd'}])
    records(W,'Tag',[{'id':301,'group_id':1,'name':'Policy','description':'Policy: update Review tag description to Reviewed and approved. and color to #008800. Create Approved tag. Keep Reference unchanged.'},{'id':302,'group_id':1,'name':'Review','description':'Pending review.','color':'#000000'},{'id':303,'group_id':1,'name':'Reference','description':'Retain reference tag.'},{'id':304,'group_id':2,'name':'Other group tag','description':'Other group metadata.'}])
    steps=[(APP,'tag_update',{'id':302,'name':'Review','description':'Reviewed and approved.'}),(APP,'tag_update',{'id':302,'name':'Review','color':'#008800'}),(APP,'tag_create',{'name':'Approved','description':'Approved tag.'})]
    preds=[('description','Tag description updated.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',302),F('description','eq','Reviewed and approved.')))),False),('color','Tag color updated.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',302),F('color','eq','#008800')))),False),('create','Tag created.',CNT(SEL(NS(APP,'Tag'),AND(F('name','eq','Approved'),F('group_id','eq',1)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',303),F('description','eq','Retain reference tag.')))),True)]
    return steps,preds
