"""Source-bound thelounge adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='thelounge';NEW_SERVER={APP:'irc_history_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Channel']]}
NEW_NOTES={APP:'{p}__ sign_in(name,password) uses original User identity. message_get(target,lastId) reads Message.msg policy; target is an unused address helper. channel_send_message(target,text,network,channel,time) inserts a local message record. network_get(uuid), network_edit(uuid,name), network_quit(network=<uuid>) operate existing network configuration rows. UUID remains text. No real IRC connection, delivery, file upload bytes or server command execution. Source signed-in users share unowned network/history records.'}
LOGIN={APP:('sign_in','name')};SERVER.update(NEW_SERVER);PFX[APP]='thelounge';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('message_get', {'target': 2, 'lastId': 201}), ('network_get', {'uuid': 'net-review'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Network',[{'id':101,'uuid':'net-policy','host':'irc.example.invalid','name':'Policy'},{'id':102,'uuid':'net-review','host':'irc.example.invalid','name':'Review'},{'id':103,'uuid':'net-reference','host':'irc.example.invalid','name':'Reference'}])
    records(W,'Message',[{'id': 201, 'network': 'net-policy', 'channel': 'general', 'time': 1, 'type': 'message', 'msg': 'Policy: rename network net-review to Reviewed. Log Approved review. and Review complete. messages. Keep Reference unchanged.'}, {'id': 202, 'network': 'net-review', 'channel': 'general', 'time': 2, 'type': 'message', 'msg': 'Pending review.'}, {'id': 203, 'network': 'net-review', 'channel': 'general', 'time': 3, 'type': 'message', 'msg': 'Retain reference message.'}])
    steps=[('__APP__', 'network_edit', {'uuid': 'net-review', 'name': 'Reviewed'}), ('__APP__', 'channel_send_message', {'target': 2, 'text': 'Approved review.', 'network': 'net-review', 'channel': 'general', 'time': 4}), ('__APP__', 'channel_send_message', {'target': 2, 'text': 'Review complete.', 'network': 'net-review', 'channel': 'general', 'time': 5})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Network'),AND(F('uuid','eq','net-review'),F('name','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Message'),F('msg','eq','Approved review.'))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Message'),F('msg','eq','Review complete.'))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Message'),AND(F('id','eq',203),F('msg','eq','Retain reference message.')))),True))
    return steps,preds
