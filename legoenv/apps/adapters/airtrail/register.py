"""Source-bound airtrail adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='airtrail';NEW_SERVER={APP:'flight_log_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Airport', 'Aircraft', 'Airline']]}
NEW_NOTES={APP:'{p}__ user_login(username,password). flight_get(id) reads Flight.note policy; flight_list() lists source metadata. flight_create(from_id,to_id,date,flight_number,note) inserts a Flight plus source passenger row for caller. flight_update(id,note,flight_number), flight_delete(id) edit/delete records; source owner/admin OR passenger access retained. flight_list scope/userId do not filter source and can expose unrelated records. No booking, live aviation/weather/tracks, OAuth or actual travel effect certified.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='airtrail';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('flight_get', {'id': 201}), ('flight_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Flight',[{'id':201,'from_id':1,'to_id':2,'date':'2026-10-20','date_precision':'day','flight_number':'POLICY','note':'Policy: update flight 202 note to Reviewed and approved. and flight number to REVIEWED. Log flight APPROVED from airports 1 to 2 on 2026-10-20. Keep Reference unchanged.'},{'id':202,'from_id':1,'to_id':2,'date':'2026-10-20','date_precision':'day','flight_number':'PENDING','note':'Pending review.'},{'id':203,'from_id':1,'to_id':2,'date':'2026-10-20','date_precision':'day','flight_number':'REFERENCE','note':'Retain reference flight.'}])
    steps=[(APP,'flight_update',{'id':202,'note':'Reviewed and approved.'}),(APP,'flight_update',{'id':202,'flight_number':'REVIEWED'}),(APP,'flight_create',{'from_id':1,'to_id':2,'date':'2026-10-20','flight_number':'APPROVED','note':'Approved flight record.'})]
    preds=[('note','Flight note updated.',CNT(SEL(NS(APP,'Flight'),AND(F('id','eq',202),F('note','eq','Reviewed and approved.')))),False),('number','Flight number updated.',CNT(SEL(NS(APP,'Flight'),AND(F('id','eq',202),F('flight_number','eq','REVIEWED')))),False),('create','Flight record created.',CNT(SEL(NS(APP,'Flight'),AND(F('flight_number','eq','APPROVED'),F('from_id','eq',1),F('to_id','eq',2)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Flight'),AND(F('id','eq',203),F('note','eq','Retain reference flight.')))),True)]
    return steps,preds
