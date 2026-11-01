"""Original 4gaBoards card creation, scalar edits, tasks and comments."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='4gaboards';NEW_SERVER={APP:'kanban'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','UserPrefs','Core')]}
NEW_NOTES={APP:('{p}__ is 4gaBoards. Sign in with {p}__sign_in(email,password), as User 1. '
    'list_projects returns ProjectManager links; get_board(id) and get_card(id) read scalar metadata. Card.description carries policy. '
    'create_card(listId,name,description,position,dueDate) creates a card on the List and its Board. '
    'update_card(id,name,description,dueDate,position) updates scalar fields; listId does not move the card. '
    'create_task(cardId,name,isCompleted,dueDate), update_task(id,name,isCompleted,dueDate) write task fields; delete_task(id) removes a task. '
    'create_comment(cardId,text), update_comment(id,text) store scalar text in Comment.data; list_comments(cardId) lists that card only. '
    'delete_comment(id) marks deleted_at but list_comments still returns marked rows. move_card_to_completed(id,isCompleted) updates completion state, retaining timestamps when reopened. '
    'delete_card does not implement deletion. Full board/project permissions, cross-list movement, imports/sync, notifications and binary attachments are not certified.')}
LOGIN={APP:('sign_in','email')}
SERVER.update(NEW_SERVER);PFX[APP]='4gaboards';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    reads=[('list_projects',{})]+[('get_board',{'id':r['id']}) for r in env.state.get(NS(APP,'Board'),[])]
    for r in env.state.get(NS(APP,'Card'),[]):reads.extend([('get_card',{'id':r['id']}),('list_comments',{'cardId':r['id']})])
    for tool,args in reads:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def workspace(W,src=None):
    _append(W,'Project',[{'id':10,'name':'Operations project','created_by_id':1}],src)
    _append(W,'ProjectManager',[{'id':10,'project_id':10,'user_id':1,'created_by_id':1}],src)
    _append(W,'ProjectMembership',[{'id':10,'project_id':10,'user_id':1}],src)
    _append(W,'Board',[{'id':20,'project_id':10,'name':'Operations board','position':0,'created_by_id':1}],src)
    _append(W,'BoardMembership',[{'id':20,'board_id':20,'user_id':1,'role':'editor','can_comment':True,'created_by_id':1}],src)
    _append(W,'List',[{'id':30,'board_id':20,'name':'Review','position':0,'is_completed':False,'created_by_id':1},{'id':31,'board_id':20,'name':'Done','position':1,'is_completed':True,'created_by_id':1}],src)
def cards(W,rows,src=None):return _append(W,'Card',[{'board_id':20,'list_id':30,'position':0,'is_completed':False,'created_by_id':1,**r} for r in rows],src)
def tasks(W,rows,src=None):return _append(W,'Task',[{'is_completed':False,'position':0,'created_by_id':1,**r} for r in rows],src)
def comments(W,rows,src=None):return _append(W,'Comment',[{'user_id':1,'created_by_id':1,**r} for r in rows],src)
def smoke_seed(W):
    workspace(W)
    cards(W,[{'id':101,'name':'Review policy','description':'Policy: record the approved review wording on card102, mark it completed and add a review comment. Keep card103 reference description unchanged.'},
        {'id':102,'name':'Review checklist','description':'Review pending.'},{'id':103,'name':'Reference card','description':'Retain this reference wording.'}])
    tasks(W,[{'id':201,'card_id':102,'name':'Existing review task'}])
    comments(W,[{'id':301,'card_id':101,'data':{'text':'Existing policy comment.'}}])
    steps=[(APP,'update_card',{'id':102,'description':'Review approved and recorded.'}),(APP,'move_card_to_completed',{'id':102,'isCompleted':True}),(APP,'create_comment',{'cardId':102,'text':'Review complete; approval recorded.'})]
    preds=[('description','Review description approved.',CNT(SEL(NS(APP,'Card'),AND(F('id','eq',102),F('description','eq','Review approved and recorded.')))),False),
        ('completed','Review card completed.',CNT(SEL(NS(APP,'Card'),AND(F('id','eq',102),F('is_completed','eq',True)))),False),
        ('comment','Review comment recorded.',CNT(SEL(NS(APP,'Comment'),AND(F('card_id','eq',102),F('data','eq','Review complete; approval recorded.')))),False),
        ('reference','Reference description unchanged.',CNT(SEL(NS(APP,'Card'),AND(F('id','eq',103),F('description','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','workspace','cards','tasks','comments','smoke_seed']
