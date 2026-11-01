"""Source-bound bugsink adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='bugsink';NEW_SERVER={APP:'team_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). auth_token_list() reads genuine AuthToken.description policy under original superuser guard. team_create(name,visibility), team_edit(team_pk,name,visibility), team_delete(team_pk) operate native Team rows. Creation does not insert a membership. No real auth token issuance, events ingestion, notifications/email or external effects.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='bugsink';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('auth_token_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Team',[{'id':101,'name':'Operations','visibility':99},{'id':102,'name':'Pending','visibility':1},{'id':103,'name':'Reference','visibility':99}])
    records(W,'AuthToken',[{'id': 201, 'token': 'fixture-policy', 'description': 'Policy: rename team102 to Reviewed, set visibility99, create Approved team. Keep Reference unchanged.'}, {'id': 202, 'token': 'fixture-review', 'description': 'Review token context.'}, {'id': 203, 'token': 'fixture-reference', 'description': 'Retain reference description.'}])
    steps=[('__APP__', 'team_edit', {'team_pk': 102, 'name': 'Reviewed'}), ('__APP__', 'team_edit', {'team_pk': 102, 'visibility': 99}), ('__APP__', 'team_create', {'name': 'Approved', 'visibility': 99})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Team'),AND(F('id','eq',102),F('name','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Team'),AND(F('id','eq',102),F('visibility','eq',99)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Team'),AND(F('name','eq','Approved'),F('visibility','eq',99)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'AuthToken'),AND(F('id','eq',203),F('description','eq','Retain reference description.')))),True))
    return steps,preds
