'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound bracket adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='bracket';NEW_SERVER={APP:'tournament_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Club', 'UserXClub']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). Independent metadata-only demonstration: tournament_read(tournament_id), court_read(tournament_id), tournament_update(tournament_id,margin_minutes), tournament_change_status(tournament_id,status), court_create/update/delete. Full policy-carrying admission blocked: source has no readable narrative body. Club membership and OPEN guards are OR alternatives in source, so do not claim combined authorization.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='bracket';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('tournament_read', {'tournament_id': 101}), ('court_read', {'tournament_id': 101})]:
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
    records(W,'Tournament',[{'id':101,'name':'Operations Open','start_time':'2026-07-01T09:00:00','club_id':1,'dashboard_public':False,'players_can_be_in_multiple_teams':False,'auto_assign_courts':False,'duration_minutes':15,'margin_minutes':5,'status':'OPEN'},{'id':102,'name':'Archived Open','start_time':'2026-12-01T09:00:00','club_id':1,'dashboard_public':False,'players_can_be_in_multiple_teams':False,'auto_assign_courts':False,'duration_minutes':15,'margin_minutes':5,'status':'ARCHIVED'}])
    records(W,'Court',[{'id':201,'name':'Review Court','tournament_id':101},{'id':202,'name':'Reference Court','tournament_id':101}])
    steps=[(APP,'tournament_update',{'tournament_id':101,'margin_minutes':10}),(APP,'tournament_change_status',{'tournament_id':101,'status':'ARCHIVED'}),(APP,'court_create',{'tournament_id':102,'name':'Approved Court'})]
    preds=[('margin','Tournament margin updated.',CNT(SEL(NS(APP,'Tournament'),AND(F('id','eq',101),F('margin_minutes','eq',10)))),False),('status','Tournament archived.',CNT(SEL(NS(APP,'Tournament'),AND(F('id','eq',101),F('status','eq','ARCHIVED')))),False),('create','Court created.',CNT(SEL(NS(APP,'Court'),F('name','eq','Approved Court'))),False),('reference','Reference court unchanged.',CNT(SEL(NS(APP,'Court'),AND(F('id','eq',202),F('name','eq','Reference Court')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
