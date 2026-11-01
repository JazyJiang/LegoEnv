"""Source-bound october adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='october';NEW_SERVER={APP:'october_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['BackendUser', 'UserRole', 'UserGroup', 'MailLayout']]}
NEW_NOTES={APP:'{p}__ sign_in(login,password). mailtemplate_ontest(id=201) native fetch returns content_text; only row-read effect is certified, no test mail delivery. mailtemplate_create(code,subject,description,content_html,content_text), mailtemplate_update(id,subject,content_text), mailtemplate_delete(id) edit local templates. Delete only checks is_custom and is anonymous in source.'}
LOGIN={APP:('sign_in','login')};SERVER.update(NEW_SERVER);PFX[APP]='october';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'login':self.persona,'password':self.password}).get('ok')
    for t,args in [('mailtemplate_ontest', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'MailTemplate',[{'id': 201, 'code': 'policy', 'subject': 'Policy', 'description': 'Operations policy template', 'content_html': '<p>Policy</p>', 'content_text': 'Policy: update template202 content_text to Reviewed and approved. and subject Reviewed. Create approved template. Keep Reference unchanged.', 'is_custom': True}, {'id': 202, 'code': 'review', 'subject': 'Pending', 'description': 'Review', 'content_html': '<p>Pending</p>', 'content_text': 'Pending review.', 'is_custom': True}, {'id': 203, 'code': 'reference', 'subject': 'Reference', 'description': 'Reference', 'content_html': '<p>Reference</p>', 'content_text': 'Retain reference template.', 'is_custom': False}])
    steps=[('__APP__', 'mailtemplate_update', {'id': 202, 'content_text': 'Reviewed and approved.', 'subject': 'Reviewed'}), ('__APP__', 'mailtemplate_create', {'code': 'approved', 'subject': 'Approved', 'description': 'Probe template', 'content_html': '<p>Probe</p>', 'content_text': 'Approved template.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'MailTemplate'),AND(F('id','eq',202),F('content_text','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'MailTemplate'),AND(F('id','eq',202),F('subject','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'MailTemplate'),AND(F('code','eq','approved'),F('content_text','eq','Approved template.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'MailTemplate'),AND(F('id','eq',203),F('content_text','eq','Retain reference template.')))),True))
    return steps,preds
