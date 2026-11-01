"""Source-bound osem adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='osem';NEW_SERVER={APP:'osem_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'UsersRole']]}
NEW_NOTES={APP:'{p}__ sign_in(username,encrypted_password) native panel. conference_show(id=201) reads description. Site-admin conference_create(title,short_title,timezone,start_date,end_date,description) and conference_update(id,title,description) are local metadata writes. No automatic side effects absent from executor are claimed.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='osem';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'encrypted_password':self.password}).get('ok')
    for t,args in [('conference_show', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Conference',[{'id': 201, 'title': 'Policy', 'short_title': 'policy', 'description': 'Policy: update conference202 description to Reviewed and approved. and title Reviewed. Create Approved conference. Keep Reference unchanged.'}, {'id': 202, 'title': 'Pending', 'short_title': 'pending', 'description': 'Pending review.'}, {'id': 203, 'title': 'Reference', 'short_title': 'reference', 'description': 'Retain reference conference.'}])
    steps=[('__APP__', 'conference_update', {'id': 202, 'description': 'Reviewed and approved.', 'title': 'Reviewed'}), ('__APP__', 'conference_create', {'title': 'Approved', 'short_title': 'approved', 'timezone': 'UTC', 'start_date': '2026-11-01T09:00:00', 'end_date': '2026-11-02T17:00:00', 'description': 'Approved conference.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Conference'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Conference'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Conference'),AND(F('short_title','eq','approved'),F('title','eq','Approved')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Conference'),AND(F('id','eq',203),F('description','eq','Retain reference conference.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'username':W.persona,'encrypted_password':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
