"""Source-bound zammad adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='zammad';NEW_SERVER={APP:'helpdesk_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'Role', 'Permission', 'GroupUser', 'RoleUser', 'TicketStateType', 'TicketState', 'TicketPriority', 'TicketArticleType', 'TicketArticleSender']]}
NEW_NOTES={APP:'{p}__ uses sign_in(login,password). ticketarticle_index_by_ticket(id) reads TicketArticle.body policy; ticket_show(id) reads ticket metadata. ticketarticle_create(ticket_id,body,internal) appends an article record; ticket_update_title(id,title) changes title; ticketarticle_update(id,internal) changes only internal flag, not body; ticketarticle_destroy(id) deletes a record. Source lacks auth/role/customer checks on many of these calls; no full helpdesk ACL or actual outbound email/chat/AI delivery certified.'}
LOGIN={APP:('sign_in','login')};SERVER.update(NEW_SERVER);PFX[APP]='zammad';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'login':self.persona,'password':self.password}).get('ok')
    for t,args in [('ticketarticle_index_by_ticket', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Ticket',[{'id':201,'group_id':1,'priority_id':1,'state_id':1,'owner_id':1,'customer_id':4,'title':'Pending review'}]);records(W,'TicketArticle',[{'id':301,'ticket_id':201,'type_id':1,'sender_id':1,'body':'Policy: set ticket201 title Reviewed operations; mark article302 internal=true; append Reviewed and approved. article. Keep reference article303 body unchanged.','internal':True},{'id':302,'ticket_id':201,'type_id':1,'sender_id':1,'body':'Review context.','internal':False},{'id':303,'ticket_id':201,'type_id':1,'sender_id':1,'body':'Retain reference article body.','internal':True}])
    steps=[(APP,'ticket_update_title',{'id':201,'title':'Reviewed operations'}),(APP,'ticketarticle_update',{'id':302,'internal':True}),(APP,'ticketarticle_create',{'ticket_id':201,'type_id':1,'sender_id':1,'body':'Reviewed and approved.','internal':True})]
    preds=[('title','Ticket title updated.',CNT(SEL(NS(APP,'Ticket'),AND(F('id','eq',201),F('title','eq','Reviewed operations')))),False),('internal','Article internal flag changed.',CNT(SEL(NS(APP,'TicketArticle'),AND(F('id','eq',302),F('internal','eq',True)))),False),('article','Article body appended.',CNT(SEL(NS(APP,'TicketArticle'),AND(F('ticket_id','eq',201),F('body','eq','Reviewed and approved.')))),False),('reference','Reference body unchanged.',CNT(SEL(NS(APP,'TicketArticle'),AND(F('id','eq',303),F('body','eq','Retain reference article body.')))),True)]
    return steps,preds
