"""NodeBB original room-message and group metadata panel."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='nodebb';NEW_SERVER={APP:'forum_chat'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name']!='User']}
NEW_NOTES={APP:('{p}__ is forum/chat metadata. sign_in(username,password) verifies User1. chat_list lists your membership rows; chat_get(roomId) reads a known room; chatmessage_list(roomId) reads messages and ChatMessage.content carries policy. chat_post(roomId,message) inserts message records in an existing member room; chatmessage_edit(roomId,mid,message) and chatmessage_delete(roomId,mid) change text/deleted scalar. chat_rename(roomId,name), chat_invite(roomId,uid), chat_kick(roomId,uid) operate room/member metadata. group_search(query) reads groups, group_create(name,description), group_update(name,description) write scalar metadata. Source ACL predicates are incomplete; no full moderation or network message delivery is certified. topic_post omits initial Post and post_edit records a blank diff without replacing content.')}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='nodebb';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('chat_list',{}),('group_search',{})]+[('chatmessage_list',{'roomId':r['roomId']}) for r in env.state.get(NS(APP,'ChatRoom'),[])]
    for t,args in reads:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def rooms(W,rows,src=None):return _append(W,'ChatRoom',rows,src)
def messages(W,rows,src=None):return _append(W,'ChatMessage',rows,src)
def smoke_seed(W):
    rooms(W,[{'id':101,'roomId':101,'roomName':'Review room','public':1}]);_append(W,'RoomMember',[{'id':301,'roomId':101,'uid':1,'isOwner':True}]);_append(W,'Group',[{'id':401,'name':'review-group','description':'Pending review.'}])
    messages(W,[{'id':201,'mid':201,'roomId':101,'fromuid':1,'system':0,'content':'Policy: post Reviewed and approved. in room101; rename room101 to Reviewed operations; update review-group description to Approved group. Keep reference message203 unchanged.'},{'id':202,'mid':202,'roomId':101,'fromuid':1,'system':0,'content':'Review context.'},{'id':203,'mid':203,'roomId':101,'fromuid':2,'system':0,'content':'Reference message retained.'}])
    steps=[(APP,'chat_post',{'roomId':101,'message':'Reviewed and approved.'}),(APP,'chat_rename',{'roomId':101,'name':'Reviewed operations'}),(APP,'group_update',{'name':'review-group','description':'Approved group.'})]
    preds=[('message','Approved message record inserted.',CNT(SEL(NS(APP,'ChatMessage'),AND(F('roomId','eq',101),F('content','eq','Reviewed and approved.')))),False),('room','Room renamed.',CNT(SEL(NS(APP,'ChatRoom'),AND(F('roomId','eq',101),F('roomName','eq','Reviewed operations')))),False),('group','Group description updated.',CNT(SEL(NS(APP,'Group'),AND(F('name','eq','review-group'),F('description','eq','Approved group.')))),False),('reference','Reference message unchanged.',CNT(SEL(NS(APP,'ChatMessage'),AND(F('mid','eq',203),F('content','eq','Reference message retained.')))),True)]
    return steps,preds
