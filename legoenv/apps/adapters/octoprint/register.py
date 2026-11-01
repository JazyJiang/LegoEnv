"""Source-bound octoprint adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='octoprint';NEW_SERVER={APP:'group_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Permission']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password) as source administrator; group_list() and group_get(key) read Group.description policy. group_add(key,name,description,changeable,removable), group_update(key,description,default), group_remove(key) act on Group metadata. Source ADMIN, changeable and removable checks retained. No printer control, gcode, file bytes or timelapse rendering is certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='octoprint';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('group_list', {}), ('group_get', {'key': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Group',packlib.base(APP)['seed_state']['Group'])
    records(W,'Group',[{'id':201,'key':'policy','name':'Policy','description':'Policy: update review group description to Reviewed and approved. and default true. Create approved group. Keep reference unchanged.','permissions':[],'subgroups':[],'default':False,'changeable':False,'removable':False},{'id':202,'key':'review','name':'Review','description':'Pending review.','permissions':[],'subgroups':[],'default':False,'changeable':True,'removable':True},{'id':203,'key':'reference','name':'Reference','description':'Retain reference group.','permissions':[],'subgroups':[],'default':False,'changeable':False,'removable':False}])
    steps=[(APP,'group_update',{'key':'review','description':'Reviewed and approved.'}),(APP,'group_update',{'key':'review','default':True}),(APP,'group_add',{'key':'approved','name':'Approved','description':'Approved group.','changeable':True,'removable':True})]
    preds=[('description','Group description updated.',CNT(SEL(NS(APP,'Group'),AND(F('key','eq','review'),F('description','eq','Reviewed and approved.')))),False),('default','Group default updated.',CNT(SEL(NS(APP,'Group'),AND(F('key','eq','review'),F('default','eq',True)))),False),('create','Group created.',CNT(SEL(NS(APP,'Group'),F('key','eq','approved'))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Group'),AND(F('key','eq','reference'),F('description','eq','Retain reference group.')))),True)]
    return steps,preds
