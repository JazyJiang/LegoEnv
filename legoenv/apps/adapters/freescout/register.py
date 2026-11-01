"""Source-bound freescout adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='freescout';NEW_SERVER={APP:'freescout_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Mailbox', 'MailboxUser', 'Folder']]}
NEW_NOTES={APP:'{p}__ user_login(email,password). customer_ajaxsearch(q=Policy) returns genuine Customer.notes policy with native staff guard. customer_create(action=create,first_name,last_name,email) creates metadata plus local Email row; customer_update(id,first_name,notes) edits internal customer records. MailboxUser predicate permits updates without target binding; original invited user has no mailbox and cannot update. No message/email reply or delivery is executed.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='freescout';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('customer_ajaxsearch', {'q': 'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Customer',[{'id': 201, 'first_name': 'Policy', 'last_name': 'Customer', 'notes': 'Policy: update customer202 notes to Reviewed and approved. and first name Reviewed. Create Approved Customer with approved@example.invalid. Keep Reference unchanged.'}, {'id': 202, 'first_name': 'Pending', 'last_name': 'Customer', 'notes': 'Pending review.'}, {'id': 203, 'first_name': 'Reference', 'last_name': 'Customer', 'notes': 'Retain reference customer.'}])
    steps=[('__APP__', 'customer_update', {'id': 202, 'notes': 'Reviewed and approved.', 'first_name': 'Reviewed'}), ('__APP__', 'customer_create', {'action': 'create', 'first_name': 'Approved', 'last_name': 'Customer', 'email': 'approved@example.invalid'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',202),F('notes','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',202),F('first_name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('first_name','eq','Approved'),F('last_name','eq','Customer')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',203),F('notes','eq','Retain reference customer.')))),True))
    return steps,preds
