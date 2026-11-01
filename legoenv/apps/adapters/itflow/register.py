"""Original ITFlow ticket/task subset; full base keeps every source tool."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='itflow';NEW_SERVER={APP:'ticket_management'}
KEEP=('sign_in','ticket_','ticketreply_','task_')
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','UserRole','Client')]}
NEW_NOTES={APP:('{p}__ is ITFlow ticket/task management. Sign in with {p}__sign_in(username=<email>,password), as User 1; source email-only login input is ignored by the executor. '
    'The active panel contains 51 original login/ticket/reply/task tools; the full 492-tool source is retained in the base. '
    'ticket_search(q,client_id,assigned,status=[ids]) filters actual ticket fields; ticket_read(ticket_id) reads a ticket. Ticket.ticket_details carries policy. '
    'ticket_create(client_id,subject,details) creates scalar ticket fields; ticket numbering/default/SLA/URL generation is incomplete. '
    'ticket_update(ticket_id,subject,details,priority) updates fields. task_create(ticket_id,name) adds a linked task; task_complete(complete_task=<Task.task_id>) sets completion timestamp. '
    'ticket_resolve(resolve_ticket), ticket_close(close_ticket), ticket_reopen(reopen_ticket) write statuses 4,5,2. '
    'task_delete(delete_task), ticket_delete(delete_ticket) remove rows. Business ticket_id/task_id match internal integer ids for created rows. '
    'Reply sending, bulk operations, notifications, numbering/SLA calculations and full client ACLs are not certified.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='itflow';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old_merge=World.merge
def _merge(self):
    if APP not in self.apps:return _old_merge(self)
    original=self.spec[APP]['tools']
    selected=[t for t in original if t['tool'].startswith(KEEP)]
    self.spec[APP]['tools']=selected
    try:return _old_merge(self)
    finally:self.spec[APP]['tools']=original
World.merge=_merge
_old_obs=World.obs_report
def _obs(self):
    rep,bad=_old_obs(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('ticket_search',{})]+[('ticket_read',{'ticket_id':r['ticket_id']}) for r in env.state.get(NS(APP,'Ticket'),[])]
    for tool,args in reads:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,pk,rows,src=None):
    rows=[{'id':r[pk],**r} for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def tickets(W,rows,src=None):return _append(W,'Ticket','ticket_id',[{'ticket_client_id':1,'ticket_created_by':1,'ticket_number':r['ticket_id'],'ticket_status':1,**r} for r in rows],src)
def tasks(W,rows,src=None):return _append(W,'Task','task_id',rows,src)
def smoke_seed(W):
    tickets(W,[{'ticket_id':101,'ticket_subject':'Review policy','ticket_details':'Policy: update the reviewed ticket wording, create a follow-up task and mark it resolved. Keep the reference details unchanged.'},
        {'ticket_id':102,'ticket_subject':'Review ticket','ticket_details':'Review pending.'},{'ticket_id':103,'ticket_subject':'Reference ticket','ticket_details':'Retain this reference wording.'}])
    tasks(W,[{'task_id':201,'task_ticket_id':101,'task_name':'Existing policy checklist'}])
    steps=[(APP,'ticket_update',{'ticket_id':102,'subject':'Reviewed ticket','details':'Review approved and recorded.'}),
        (APP,'task_create',{'ticket_id':102,'name':'Follow up approved review'}),(APP,'ticket_resolve',{'resolve_ticket':102})]
    preds=[('details','Approved ticket details recorded.',CNT(SEL(NS(APP,'Ticket'),AND(F('ticket_id','eq',102),F('ticket_details','eq','Review approved and recorded.')))),False),
        ('task','Follow-up task linked to ticket.',CNT(SEL(NS(APP,'Task'),AND(F('task_ticket_id','eq',102),F('task_name','eq','Follow up approved review')))),False),
        ('resolved','Reviewed ticket resolved.',CNT(SEL(NS(APP,'Ticket'),AND(F('ticket_id','eq',102),F('ticket_status','eq',4)))),False),
        ('reference','Reference details unchanged.',CNT(SEL(NS(APP,'Ticket'),AND(F('ticket_id','eq',103),F('ticket_details','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','tickets','tasks','smoke_seed']
