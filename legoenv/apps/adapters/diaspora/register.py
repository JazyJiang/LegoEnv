"""Source-bound diaspora adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='diaspora';NEW_SERVER={APP:'social_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Person', 'Profile', 'Role', 'Pod']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(username,password); regular User1 corresponds to Person1 by asserted source seed relation. read_stream() and get_post(id) read public Post.text policy. create_status_message(text,public) creates a Post record. create_aspect(name), update_aspect(id,name), delete_aspect(id) require own aspects. create_comment(post_id,text) inserts a comment. create_conversation(subject) only creates metadata; send_message(conversation_id,text) inserts Message, api_list_messages(conversation_id) reads it. mark_notification_read(id,set_unread=false) changes your notification. No federation, delivery or complete conversation participant/visibility ACL is certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='diaspora';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('read_stream', {}), ('api_list_messages', {'conversation_id': 401})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Post',[{'id':201,'author_id':1,'public':True,'text':'Policy: create a public post with Reviewed and approved.; create aspect Reviewed operations; send Review recorded. to conversation401. Keep reference post203 unchanged.'},{'id':202,'author_id':1,'public':True,'text':'Review context.'},{'id':203,'author_id':2,'public':True,'text':'Retain this reference post.'}]);records(W,'Conversation',[{'id':401,'author_id':1,'subject':'Review coordination'}])
    steps=[(APP,'create_status_message',{'text':'Reviewed and approved.','public':True}),(APP,'create_aspect',{'name':'Reviewed operations'}),(APP,'send_message',{'conversation_id':401,'text':'Review recorded.'})]
    preds=[('post','Public Post record created.',CNT(SEL(NS(APP,'Post'),AND(F('text','eq','Reviewed and approved.'),F('author_id','eq',1),F('public','eq',True)))),False),('aspect','Owned aspect created.',CNT(SEL(NS(APP,'Aspect'),AND(F('name','eq','Reviewed operations'),F('user_id','eq',1)))),False),('message','Conversation message persisted.',CNT(SEL(NS(APP,'Message'),AND(F('conversation_id','eq',401),F('text','eq','Review recorded.')))),False),('reference','Reference post unchanged.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',203),F('text','eq','Retain this reference post.')))),True)]
    return steps,preds
