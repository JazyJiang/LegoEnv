"""Source-bound rocket_chat adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='rocket_chat';NEW_SERVER={APP:'rocket_chat_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Users', 'Rooms', 'Subscriptions', 'Roles', 'Permissions', 'Settings']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). chat_getmessages(roomId) reads Messages.msg policy under existing membership. chat_postmessage(roomId,text) inserts message. chat_pinmessage(messageId,msg) sets actual msg and pinned fields; native chat_update text alias is ignored. chat_delete(roomId,msgId) deletes. Source role user/admin permission alternatives are global, and delete ignores roomId consistency. No real chat delivery or attachments.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='rocket_chat';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('chat_getmessages', {'roomId': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Messages',[{'id': 201, '_id': 201, 'rid': 1, 'u': 1, 'msg': 'Policy: update message202 msg to Reviewed and approved. and pin it. Post Approved review. to room1. Keep Reference unchanged.', 'ts': '2026-01-01T00:00:00', 'pinned': False}, {'id': 202, '_id': 202, 'rid': 1, 'u': 1, 'msg': 'Pending review.', 'ts': '2026-01-01T00:00:00', 'pinned': False}, {'id': 203, '_id': 203, 'rid': 1, 'u': 1, 'msg': 'Retain reference message.', 'ts': '2026-01-01T00:00:00', 'pinned': False}])
    steps=[('__APP__', 'chat_pinmessage', {'messageId': 202, 'msg': 'Reviewed and approved.'}), ('__APP__', 'chat_postmessage', {'roomId': 1, 'text': 'Approved review.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Messages'),AND(F('_id','eq',202),F('msg','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Messages'),AND(F('_id','eq',202),F('pinned','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Messages'),AND(F('rid','eq',1),F('msg','eq','Approved review.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Messages'),AND(F('_id','eq',203),F('msg','eq','Retain reference message.')))),True))
    return steps,preds
