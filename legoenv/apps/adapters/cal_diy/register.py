"""Source-bound cal_diy adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='cal_diy';NEW_SERVER={APP:'schedule_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserPassword', 'Team', 'Membership']]}
NEW_NOTES={APP:'{p}__ auth_signin(email,password). eventtype_list() or eventtype_get(id) reads EventType.description policy; schedule_getallschedulesbyuserid() lists owned schedules. schedule_create(name), schedule_update(scheduleId,name,timeZone), schedule_delete(scheduleId) operate Schedule metadata only. Source update checks owner; delete only checks caller owns at least two schedules, not target owner; eventtype_get fetch ignores owner scope. No booking/calendar delivery/availability time blocks certified.'}
LOGIN={APP:('auth_signin','email')};SERVER.update(NEW_SERVER);PFX[APP]='cal_diy';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_signin'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('eventtype_list', {}), ('eventtype_get', {'id': 101}), ('schedule_getallschedulesbyuserid', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    template=dict(packlib.base(APP)['seed_state']['EventType'][0]);template.update(id=101,title='Policy',slug='operations-policy',description='Policy: rename schedule 201 to Reviewed operations. and timezone UTC. Create Approved schedule. Keep Reference schedule unchanged.',scheduleId=201)
    records(W,'EventType',[template])
    records(W,'Schedule',[{'id':201,'userId':1,'name':'Review','timeZone':'Europe/London'},{'id':202,'userId':1,'name':'Reference','timeZone':'Europe/London'},{'id':203,'userId':2,'name':'Other account','timeZone':'America/New_York'}])
    steps=[(APP,'schedule_update',{'scheduleId':201,'name':'Reviewed operations.'}),(APP,'schedule_update',{'scheduleId':201,'timeZone':'UTC'}),(APP,'schedule_create',{'name':'Approved'})]
    preds=[('name','Schedule renamed.',CNT(SEL(NS(APP,'Schedule'),AND(F('id','eq',201),F('name','eq','Reviewed operations.')))),False),('timezone','Schedule timezone updated.',CNT(SEL(NS(APP,'Schedule'),AND(F('id','eq',201),F('timeZone','eq','UTC')))),False),('create','Schedule created.',CNT(SEL(NS(APP,'Schedule'),AND(F('name','eq','Approved'),F('userId','eq',1)))),False),('reference','Reference schedule retained.',CNT(SEL(NS(APP,'Schedule'),AND(F('id','eq',202),F('name','eq','Reference'),F('timeZone','eq','Europe/London')))),True)]
    return steps,preds
