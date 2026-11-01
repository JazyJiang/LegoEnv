"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='chat'
CFG={'order': 109, 'entity': 'Subscription', 'pk': 'id', 'field': 'readseqid', 'field_arg': 'read', 'id_arg': 'topic', 'write_tool': 'update_read_receipt', 'kind': 'update_record', 'initial_value': 0, 'updates': [[201, 10], [202, 20], [203, 30]], 'update_extra': {'recv': 30}, 'unique_text_fields': ['topic'], 'fixture_defaults': {'userid': 1}, 'reads': [['read_messages', {'topic': 'Fixture-204'}]], 'login_tool': 'sign_in', 'user_arg': 'uname', 'password_arg': 'secret', 'notes': '{p}__ sign_in(uname,secret). update_read_receipt(topic,recv,read) changes only your Subscription sequence counters. read_messages(topic) reads the native Message.content object with its source-existing txt field. Fresh fixture topics retain the source owner membership mode. No delivery, actual consumption, encryption or full Tinode ACL behavior claimed.', 'limitations': ['Only native Subscription.readseqid local counter updates and Message.content readback certified. No actual message delivery/read confirmation, websocket, push, byte upload, secret hashing or external effect executed.', 'Source native password parameter secret is retained; unchanged dklib callable steps record the real login. Auth.userid to User.id session identity is preserved.', 'Fresh topic/subscription fixture relations clone an existing source owner membership without changing its mode strings or any original guard; unrelated accounts receive no new membership.', 'The policy body uses only the exact existing Message.content {txt: text} shape, not an invented JSON carrier schema. Source read checks modewant membership; no complete Tinode modegiven authorization model is claimed.'], 'app': 'chat', 'account_entity': 'Auth', 'account_user_col': 'uname', 'account_password_col': 'secret', 'fixture_rows': [{'id': 201, 'topic': 'Fixture-201', 'userid': 1, 'modewant': 'JRWPSADO', 'modegiven': 'O', 'recvseqid': 3, 'readseqid': 0, 'delid': 0, 'createdat': '2026-10-20T09:00:00', 'updatedat': '2026-10-20T09:00:00'}, {'id': 202, 'topic': 'Fixture-202', 'userid': 1, 'modewant': 'JRWPSADO', 'modegiven': 'O', 'recvseqid': 3, 'readseqid': 0, 'delid': 0, 'createdat': '2026-10-20T09:00:00', 'updatedat': '2026-10-20T09:00:00'}, {'id': 203, 'topic': 'Fixture-203', 'userid': 1, 'modewant': 'JRWPSADO', 'modegiven': 'O', 'recvseqid': 3, 'readseqid': 0, 'delid': 0, 'createdat': '2026-10-20T09:00:00', 'updatedat': '2026-10-20T09:00:00'}, {'id': 204, 'topic': 'Fixture-204', 'userid': 1, 'modewant': 'JRWPSADO', 'modegiven': 'O', 'recvseqid': 3, 'readseqid': 0, 'delid': 0, 'createdat': '2026-10-20T09:00:00', 'updatedat': '2026-10-20T09:00:00'}], 'protected': [204, 0], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'related_fixture_rows': {'Topic': [{'id': 501, 'name': 'Fixture-201', 'owner': 1, 'state': 0, 'subcnt': 3, 'seqid': 3, 'delid': 0, 'usebt': False}, {'id': 502, 'name': 'Fixture-202', 'owner': 1, 'state': 0, 'subcnt': 3, 'seqid': 3, 'delid': 0, 'usebt': False}, {'id': 503, 'name': 'Fixture-203', 'owner': 1, 'state': 0, 'subcnt': 3, 'seqid': 3, 'delid': 0, 'usebt': False}, {'id': 504, 'name': 'Fixture-204', 'owner': 1, 'state': 0, 'subcnt': 3, 'seqid': 3, 'delid': 0, 'usebt': False}], 'Message': [{'id': 601, 'topic': 'Fixture-204', 'seqid': 1, 'from': 1, 'head': {}, 'content': {'txt': 'Policy: update the three queued records; retain this reference record unchanged.'}}]}, 'carrier': 'notes_field'}
NEW_SERVER={APP:APP+'_records'};NEW_CONTENT={APP:[CFG['entity'],'Message']}
NEW_NOTES={APP:CFG['notes']}
LOGIN={APP:(CFG['login_tool'],CFG['user_arg'])} if CFG.get('login_tool') else {}
SERVER.update(NEW_SERVER);PFX[APP]=APP;CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
def _signin(env,W):
    if not CFG.get('login_tool'):return None
    args={CFG['user_arg']:W.persona,CFG.get('password_arg','password'):W.password};args.update(CFG.get('login_extra',{}))
    return env.call(NS(APP,CFG['login_tool']),args)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    if CFG.get('login_tool'):
        result=_signin(env,self);assert result.get('ok'),result
    for tool,args in CFG.get('reads',[]):
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=copy.deepcopy(rows);assert all(isinstance(r['id'],int) for r in rows);W.seed(APP,entity,rows,src=src);return rows
def smoke_seed(W):
    records(W,CFG['entity'],CFG['fixture_rows'])
    for entity,rows in CFG['related_fixture_rows'].items():W.spec[APP]['seed_state'].setdefault(entity,[]).extend(copy.deepcopy(rows))
    steps=[];preds=[]
    for i,(identifier,value) in enumerate(CFG['updates']):
        args=dict(CFG.get('update_extra',{}));args[CFG['id_arg']]='Fixture-'+str(identifier)
        if CFG.get('field_arg'):args[CFG['field_arg']]=value
        steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
