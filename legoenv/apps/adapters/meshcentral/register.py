"""Source-bound meshcentral adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='meshcentral';NEW_SERVER={APP:'device_group_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Mesh', 'Node']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). node_getnotes(id=2001) reads genuine NodeNote.value policy. usergroup_create(name,desc,domain), usergroup_edit(ugrpid,name,desc), usergroup_delete(ugrpid) operate group metadata; source siteadmin nonzero required. User identities mapped to 1/2 with original link rights. node_getnotes lacks source auth guard. Existing node_setnotes upsert writes notes alias without updating value; not certified as body update. No remote device control or delivery effect certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='meshcentral';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('node_getnotes', {'id': 2001})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'NodeNote',[{'id':201,'_id':2001,'type':'note','value':'Policy: update group 301 description to Reviewed and approved. and name to Reviewed operations. Create Approved group. Keep reference group unchanged.'}])
    records(W,'UserGroup',[{'id':301,'_id':301,'type':'ugrp','domain':'meshcentral','name':'Review','desc':'Pending review.','links':{}},{'id':302,'_id':302,'type':'ugrp','domain':'meshcentral','name':'Reference','desc':'Retain reference group.','links':{}}])
    steps=[(APP,'usergroup_edit',{'ugrpid':301,'desc':'Reviewed and approved.'}),(APP,'usergroup_edit',{'ugrpid':301,'name':'Reviewed operations.'}),(APP,'usergroup_create',{'name':'Approved','desc':'Approved group.','domain':'meshcentral'})]
    preds=[('description','Group description updated.',CNT(SEL(NS(APP,'UserGroup'),AND(F('_id','eq',301),F('desc','eq','Reviewed and approved.')))),False),('name','Group renamed.',CNT(SEL(NS(APP,'UserGroup'),AND(F('_id','eq',301),F('name','eq','Reviewed operations.')))),False),('create','Group created.',CNT(SEL(NS(APP,'UserGroup'),F('name','eq','Approved'))),False),('reference','Reference group retained.',CNT(SEL(NS(APP,'UserGroup'),AND(F('_id','eq',302),F('desc','eq','Retain reference group.')))),True)]
    return steps,preds
