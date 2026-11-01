"""Group-Office scalar tasks, notes, events and folder/contact writes."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='groupoffice'
NEW_SERVER={APP:'groupware'}
CONFIG={'User','Group','UserGroup','Acl','AclGroup','AclGroupChange','Permission','TaskListGrouping','Module','Entity','AuthMethod'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is Group-Office. Sign in with {p}__sign_in(username,password), as User 1. '
    'note_query(q,noteBookId), task_query(q,tasklistId), event_query(q,calendarId) list scalar rows with optional substring/exact-parent filters; *_get(id) reads a row. '
    'Note.content carries policy; note_set(noteBookId,name,content) creates a new note, task_set(tasklistId,title,description,due) creates a new task. '
    'event_set(calendarId,title,start,duration,description) creates an event row; it does not send invitations, check conflicts or expand recurrences. '
    'These *_set tools are insert-only; source has no ordinary note/task/event update tools. contact_update(id,update.name,update.firstName,update.lastName,update.vatNo,update.newsletterAllowed,update.lastContactAt) updates existing scalar contact fields. '
    'folder_create(parent_id,name), folder_rename(id,name), folder_delete(id) operate on folder metadata; folder_delete hard-deletes and does not implement trash/restore. '
    'file_create(folder_id,name,extension) creates empty File metadata without bytes. folder_subfolder_list(node) and folder_filelist_search(folder_id,query) read file/folder metadata. '
    'Source filter JSON, sort/pagination, JMAP update/destroy batches, full mail delivery, binary transfer and general ACL permissions are not fully implemented. No move, sharing or full calendar synchronization capability is claimed.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='groupoffice';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
OBS_READS=['note_query','note_get','task_query','task_get','event_query','event_get','folder_subfolder_list','folder_filelist_search']
_original_obs=World.obs_report
def _obs_report(self):
    rep,bad=_original_obs(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('note_query',{}),('task_query',{}),('event_query',{})]
    for entity,tool in [('Note','note_get'),('Task','task_get'),('Event','event_get')]:
        reads.extend((tool,{'id':r['id']}) for r in env.state.get(NS(APP,entity),[]))
    for folder in env.state.get(NS(APP,'Folder'),[]):reads.extend([('folder_subfolder_list',{'node':folder['id']}),('folder_filelist_search',{'folder_id':folder['id']})])
    for tool,args in reads:
        result=env.call(NS(APP,tool),args)
        if not result.get('ok'):raise RuntimeError(f'{APP} observation {tool}: {result}')
        rep[f'{APP} {tool} '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs_report
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def workspace(W,*,notebook_id=10,tasklist_id=10,calendar_id=10,folder_id=10,src=None):
    _append(W,'NoteBook',[{'id':notebook_id,'name':'Operations notebook','createdBy':1,'aclId':1}],src)
    _append(W,'TaskList',[{'id':tasklist_id,'name':'Operations tasks','description':'Operations follow-up','createdBy':1,'ownerId':1,'aclId':1,'defaultColor':'#0000ff','groupingId':1}],src)
    _append(W,'Calendar',[{'id':calendar_id,'name':'Operations calendar','createdBy':1,'ownerId':1,'aclId':1,'defaultColor':'#0088cc'}],src)
    _append(W,'Folder',[{'id':folder_id,'parent_id':None,'name':'Operations documents','muser_id':1,'quota_user_id':1,'visible':True,'readonly':False}],src)
def notes(W,rows,src=None):return _append(W,'Note',[{'noteBookId':10,'createdBy':1,'modifiedBy':1,'password':'',**r} for r in rows],src)
def tasks(W,rows,src=None):return _append(W,'Task',[{'tasklistId':10,'createdBy':1,'responsibleUserId':1,'progress':1,'percentComplete':0,**r} for r in rows],src)
def events(W,rows,src=None):return _append(W,'Event',[{'calendarId':10,'createdBy':1,'start':W.now,'firstOccurrence':W.now,'duration':'PT1H','status':'confirmed',**r} for r in rows],src)
def contacts(W,rows,src=None):return _append(W,'Contact',[{'createdBy':1,'notes':'','isOrganization':False,**r} for r in rows],src)
def smoke_seed(W):
    workspace(W)
    notes(W,[{'id':101,'name':'Review policy','content':'Policy: write the review result as a note and create a follow-up task. Keep the reference note unchanged.'},
        {'id':102,'name':'Reference note','content':'Retain this reference wording.'},
        {'id':103,'name':'Meeting context','content':'Supplier review is scheduled for Thursday.'}])
    tasks(W,[{'id':201,'title':'Existing review','description':'Prepare review context.'}])
    events(W,[{'id':301,'title':'Existing review meeting'}])
    contacts(W,[{'id':401,'name':'Supplier contact','firstName':'Supplier','lastName':'Contact'}])
    steps=[(APP,'note_set',{'noteBookId':10,'name':'Review outcome','content':'Supplier review approved; follow-up required.'}),
        (APP,'task_set',{'tasklistId':10,'title':'Follow up approved review','description':'Record the supplier review next step.','due':'2026-10-22T09:00:00'})]
    preds=[('outcome','Review outcome note exists.',CNT(SEL(NS(APP,'Note'),AND(F('name','eq','Review outcome'),F('content','eq','Supplier review approved; follow-up required.')))),False),
        ('followup','Follow-up task exists.',CNT(SEL(NS(APP,'Task'),AND(F('title','eq','Follow up approved review'),F('tasklistId','eq',10)))),False),
        ('due','Follow-up due date is set.',CNT(SEL(NS(APP,'Task'),AND(F('title','eq','Follow up approved review'),F('due','eq','2026-10-22T09:00:00')))),False),
        ('reference','Reference note is unchanged.',CNT(SEL(NS(APP,'Note'),AND(F('id','eq',102),F('content','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','workspace','notes','tasks','events','contacts','smoke_seed']
