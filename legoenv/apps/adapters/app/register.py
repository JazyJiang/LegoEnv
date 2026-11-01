"""Source-bound app adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='app';NEW_SERVER={APP:'app_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Mailbox']]}
NEW_NOTES={APP:'{p}__ login_sign_in_web(email,password). alias_list() reads genuine Alias.note. alias_update(alias_id,note,name,pinned) writes original panel scalar fields; alias_toggle_enabled(alias_id,enabled) toggles; alias_delete(alias_id) schedules delete_on and disables alias. Native ownership retained, deleted aliases still appear in source list. No alias-create tool exists or is invented.'}
LOGIN={APP:('login_sign_in_web','email')};SERVER.update(NEW_SERVER);PFX[APP]='app';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'login_sign_in_web'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('alias_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Alias',[{'id': 201, 'user_id': 1, 'mailbox_id': 1, 'email': 'policy@example.invalid', 'name': 'Policy', 'note': 'Policy: update alias202 note to Reviewed and approved. and name Reviewed and pinned true. Keep Reference unchanged.', 'enabled': True, 'pinned': False}, {'id': 202, 'user_id': 1, 'mailbox_id': 1, 'email': 'review@example.invalid', 'name': 'Pending', 'note': 'Pending review.', 'enabled': True, 'pinned': False}, {'id': 203, 'user_id': 1, 'mailbox_id': 1, 'email': 'reference@example.invalid', 'name': 'Reference', 'note': 'Retain reference alias.', 'enabled': True, 'pinned': False}])
    steps=[('__APP__', 'alias_update', {'alias_id': 202, 'note': 'Reviewed and approved.', 'name': 'Reviewed', 'pinned': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('note','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('pinned','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',203),F('note','eq','Retain reference alias.')))),True))
    return steps,preds
