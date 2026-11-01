"""Source-bound koel adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='koel';NEW_SERVER={APP:'koel_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Organization', 'Role', 'ModelHasRoles']]}
NEW_NOTES={APP:'{p}__ user_login(email,password). radiostation_index() reads own RadioStation.description policy. radiostation_create(name,url,description), radiostation_update(radioStation,name,description), radiostation_destroy(radioStation) edit native metadata with ownership guards. Source update also writes placeholder logo implementation-set, no real image. No station stream fetch/audio playback/music/AI or external activity.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='koel';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('radiostation_index', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'RadioStation',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update station202 description to Reviewed and approved. and name Reviewed. Create Approved station using https://radio.invalid/approved. Keep Reference unchanged.', 'user_id': 1, 'url': 'https://radio.invalid/policy', 'is_public': False}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'user_id': 1, 'url': 'https://radio.invalid/review', 'is_public': False}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference station.', 'user_id': 1, 'url': 'https://radio.invalid/reference', 'is_public': False}])
    steps=[('__APP__', 'radiostation_update', {'radioStation': 202, 'description': 'Reviewed and approved.', 'name': 'Reviewed'}), ('__APP__', 'radiostation_create', {'name': 'Approved', 'url': 'https://radio.invalid/approved', 'description': 'Approved station.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'RadioStation'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'RadioStation'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'RadioStation'),AND(F('name','eq','Approved'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'RadioStation'),AND(F('id','eq',203),F('description','eq','Retain reference station.')))),True))
    return steps,preds
