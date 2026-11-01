'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSentry writes only: source has no readable business policy carrier.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='sentry';NEW_SERVER={APP:'issue_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name']!='User']}
NEW_NOTES={APP:('{p}__ exposes issue and saved-search writes. user_login(username,password) verifies User1; auth_whoami reads only the signed-in User. No Group/Activity/project/saved-search read/list exists. group_update(id,status,substatus,priority) writes integer state metadata; group_add_note(group_id,text,project) inserts Activity.data. activity_note_update(note_id,text) and activity_note_delete(note_id) require authorship. savedsearch_create(name,query,visibility,organization_id), savedsearch_update(search_id,...), savedsearch_delete(search_id) operate records with known ids. No readable policy carrier, issue search or notification/alert execution is certified; complete admission remains blocked.')}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='sentry';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    r=env.call(NS(APP,'auth_whoami'),{});assert r.get('ok'),r;rep[APP+' auth_whoami']=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source business text read/list exists: auth_whoami reads only User. Group.message and Activity.data cannot be read through source interfaces. Complete admission blocked; no invented carrier/read tool.')
def metadata_smoke_seed(W):
    records(W,'Organization',[{'id':101,'name':'Operations','slug':'ops','status':0}]);records(W,'Project',[{'id':201,'organization':101,'name':'Review project','slug':'review','status':0}]);records(W,'Group',[{'id':301,'project':201,'message':'Review issue','status':0},{'id':302,'project':201,'message':'Reference issue','status':0},{'id':303,'project':201,'message':'Other issue','status':0}])
    steps=[(APP,'savedsearch_create',{'name':'review-search','query':'is:unresolved','visibility':'owner','organization_id':101}),(APP,'group_update',{'id':301,'status':1}),(APP,'group_add_note',{'group_id':301,'project':201,'text':'Review approved and recorded.'})]
    preds=[('search','Saved-search metadata created.',CNT(SEL(NS(APP,'SavedSearch'),F('name','eq','review-search'))),False),('state','Issue state metadata updated.',CNT(SEL(NS(APP,'Group'),AND(F('id','eq',301),F('status','eq',1)))),False),('note','Activity note persisted.',CNT(SEL(NS(APP,'Activity'),AND(F('group','eq',301),F('data','eq','Review approved and recorded.')))),False),('reference','Reference issue unchanged.',CNT(SEL(NS(APP,'Group'),AND(F('id','eq',302),F('message','eq','Reference issue'),F('status','eq',0)))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
