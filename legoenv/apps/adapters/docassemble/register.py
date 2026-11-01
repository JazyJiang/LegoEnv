"""Source-bound docassemble adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='docassemble';NEW_SERVER={APP:'docassemble_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['UserModel', 'UserAuthModel', 'UserRoles', 'Role']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). chatlog_get_log(i,session,chat_mode) reads native ChatLog.message with owner scope; source ignores filename/session filters. chatlog_send_message(i,data) and monitor_send_chat_message(key,data,chat_user_id) only append local database log records. No websocket/chat delivery, interview state changes or model invocation.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='docassemble';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('chatlog_get_log', {'i': 'policy.yml', 'session': 'policy-session', 'chat_mode': 'peer'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'ChatLog',[{'id': 201, 'filename': 'policy.yml', 'key': 'policy-session', 'owner_id': 1, 'user_id': 1, 'message': 'Policy: append Approved1 Approved2 and Approved3 to policy.yml chat log. Keep Reference unchanged.', 'encrypted': False, 'open_to_peer': True}, {'id': 202, 'filename': 'policy.yml', 'key': 'policy-session', 'owner_id': 1, 'user_id': 1, 'message': 'Pending review.', 'encrypted': False, 'open_to_peer': True}, {'id': 203, 'filename': 'policy.yml', 'key': 'policy-session', 'owner_id': 1, 'user_id': 1, 'message': 'Retain reference message.', 'encrypted': False, 'open_to_peer': True}])
    steps=[('__APP__', 'chatlog_send_message', {'i': 'policy.yml', 'data': 'Approved1'}), ('__APP__', 'chatlog_send_message', {'i': 'policy.yml', 'data': 'Approved2'}), ('__APP__', 'chatlog_send_message', {'i': 'policy.yml', 'data': 'Approved3'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'ChatLog'),AND(F('filename','eq','policy.yml'),F('message','eq','Approved1'),F('user_id','eq',1)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'ChatLog'),AND(F('filename','eq','policy.yml'),F('message','eq','Approved2'),F('user_id','eq',1)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'ChatLog'),AND(F('filename','eq','policy.yml'),F('message','eq','Approved3'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'ChatLog'),AND(F('id','eq',203),F('message','eq','Retain reference message.')))),True))
    return steps,preds
