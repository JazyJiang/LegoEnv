"""Source-bound umami adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='umami';NEW_SERVER={APP:'analytics_board_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password). board_list(search) reads own Board.description policy. board_create(type,name,description,parameters), board_update(boardId,name,description,parameters), board_delete(boardId) operate definition metadata. Original owner/admin guards remain. No actual analytics queries, event ingestion, tracking network requests, session replay processing, dashboard rendering or scheduling certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='umami';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('board_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Board',[{'id':201,'userId':1,'type':'dashboard','name':'Review policy','description':'Policy: update board202 description Reviewed and approved. and name Reviewed operations; create Approved board. Keep board203 description unchanged.'},{'id':202,'userId':1,'type':'dashboard','name':'Pending review','description':'Pending review.'},{'id':203,'userId':1,'type':'dashboard','name':'Reference board','description':'Retain reference board description.'}])
    steps=[(APP,'board_update',{'boardId':202,'description':'Reviewed and approved.'}),(APP,'board_update',{'boardId':202,'name':'Reviewed operations'}),(APP,'board_create',{'type':'dashboard','name':'Approved board','description':'Approved board metadata'})]
    preds=[('description','Board description updated.',CNT(SEL(NS(APP,'Board'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('name','Board name updated.',CNT(SEL(NS(APP,'Board'),AND(F('id','eq',202),F('name','eq','Reviewed operations')))),False),('create','Owned board created.',CNT(SEL(NS(APP,'Board'),AND(F('name','eq','Approved board'),F('userId','eq',1)))),False),('reference','Reference board unchanged.',CNT(SEL(NS(APP,'Board'),AND(F('id','eq',203),F('description','eq','Retain reference board description.')))),True)]
    return steps,preds
