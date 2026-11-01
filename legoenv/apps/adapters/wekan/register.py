"""Source-bound wekan adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wekan';NEW_SERVER={APP:'wekan_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Board', 'List', 'Swimlane']]}
NEW_NOTES={APP:'{p}__ sign_in(username,services). card_getcard(cardId=201) reads description. card_createcard(boardId,listId,title,description) creates local cards. Native nested Board.members containment is supported: member can update/delete, nonmember cannot. Only actual source state effects are declared.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='wekan';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'services':self.password}).get('ok')
    for t,args in [('card_getcard', {'cardId': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Card',[{'id': 201, '_id': 201, 'boardId': 1, 'listId': 1, 'userId': 1, 'title': 'Policy', 'description': 'Policy: create Approved1, Approved2, Approved3 cards with approved descriptions on board1/list1. Keep Reference unchanged.'}, {'id': 202, '_id': 202, 'boardId': 1, 'listId': 1, 'userId': 1, 'title': 'Pending', 'description': 'Pending review.'}, {'id': 203, '_id': 203, 'boardId': 1, 'listId': 1, 'userId': 1, 'title': 'Reference', 'description': 'Retain reference card.'}])
    steps=[('__APP__', 'card_createcard', {'boardId': 1, 'listId': 1, 'title': 'Approved1', 'description': 'Approved card1.'}), ('__APP__', 'card_createcard', {'boardId': 1, 'listId': 1, 'title': 'Approved2', 'description': 'Approved card2.'}), ('__APP__', 'card_createcard', {'boardId': 1, 'listId': 1, 'title': 'Approved3', 'description': 'Approved card3.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Card'),AND(F('title','eq','Approved1'),F('description','eq','Approved card1.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Card'),AND(F('title','eq','Approved2'),F('description','eq','Approved card2.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Card'),AND(F('title','eq','Approved3'),F('description','eq','Approved card3.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Card'),AND(F('_id','eq',203),F('description','eq','Retain reference card.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'username':W.persona,'services':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
