"""Django CRM deal scalar writes and linked reminders; original tools retained."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='django_crm'
NEW_SERVER={APP:'crm'}
CONFIG={'User','Department','Country','Currency','Stage','ClosingReason','ContentType','City','ClientType','Industry','LeadSource','Tag','ProductCategory','TaskStage','ProjectStage','Resolution','TasksTag','TransactionQualitySignal'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is Django CRM. Sign in with {p}__sign_in(username,password), as User 1. '
    'deal_search(q) lists your deals and optionally filters name, description or next_step by substring; deal_read(id) reads a deal. '
    'Deal.description carries policy. deal_create(name,amount,next_step,next_step_date,description) creates a scalar deal owned by you. '
    'deal_update(id,amount,active,relevant,next_step,next_step_date) updates scalar fields; foreign-key changes are not implemented. '
    'deal_delete(id) deletes a deal. reminder_create(subject,reminder_date,content_type=3,object_id=<Deal id>,description) records a linked reminder; '
    'reminder_read(owner) lists reminders in your owner scope. Each create requires at least one pre-existing owned row of that entity because of the original guards. '
    'Raw CRM guards check whether any owned row exists, rather than target ownership; do not treat them as complete access control. '
    'Other source tools remain available but are not certified here; request/task/mail/file/bulk tools may have extraction placeholders or incomplete effects. '
    'No external mail delivery, binary upload, full lead conversion or bulk reassignment capability is claimed.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='django_crm';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
OBS_READS=['deal_search','deal_read','reminder_read']
_original_obs=World.obs_report
def _obs_report(self):
    rep,bad=_original_obs(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('deal_search',{}),('reminder_read',{})]
    reads.extend(('deal_read',{'id':r['id']}) for r in env.state.get(NS(APP,'Deal'),[]) if r.get('owner')==1)
    for tool,args in reads:
        result=env.call(NS(APP,tool),args)
        if not result.get('ok'):raise RuntimeError(f'{APP} observation {tool}: {result}')
        rep[f'{APP} {tool} '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs_report
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows]
    assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def deals(W,rows,src=None):
    return _append(W,'Deal',[{'owner':1,'department':1,'stage':1,'currency':1,'active':True,'amount':0,'next_step':'Review','next_step_date':W.now,'ticket':f"deal-{r['id']}",**r} for r in rows],src)
def reminders(W,rows,src=None):
    return _append(W,'Reminder',[{'owner':1,'content_type':3,'object_id':101,'active':True,'reminder_date':W.now,**r} for r in rows],src)
def smoke_seed(W):
    deals(W,[{'id':101,'name':'Quarterly renewal','amount':1200,'description':'Policy: record the approved amount and next step, then add a linked reminder. Keep the reference deal unchanged.'},
        {'id':102,'name':'Expansion review','amount':400,'description':'Awaiting approval.'},
        {'id':103,'name':'Reference deal','amount':800,'description':'Retain this reference wording.'}])
    reminders(W,[{'id':201,'subject':'Existing owner reminder','description':'Review renewal policy.'}])
    steps=[(APP,'deal_update',{'id':102,'amount':650,'next_step':'Send approved quote'}),
        (APP,'reminder_create',{'subject':'Send approved quote','description':'Approval recorded for expansion review.','reminder_date':'2026-10-22T09:00:00','content_type':3,'object_id':102})]
    preds=[('amount','Expansion amount is approved.',CNT(SEL(NS(APP,'Deal'),AND(F('id','eq',102),F('amount','eq',650)))),False),
        ('next_step','Approved next step is recorded.',CNT(SEL(NS(APP,'Deal'),AND(F('id','eq',102),F('next_step','eq','Send approved quote')))),False),
        ('reminder','Linked reminder is recorded.',CNT(SEL(NS(APP,'Reminder'),AND(F('object_id','eq',102),F('subject','eq','Send approved quote')))),False),
        ('reference','Reference wording stays unchanged.',CNT(SEL(NS(APP,'Deal'),AND(F('id','eq',103),F('description','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','deals','reminders','smoke_seed']
