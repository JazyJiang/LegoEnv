"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='phplist3'
CFG={'order': 112, 'entity': 'Message', 'pk': 'id', 'field': 'message', 'field_arg': 'message', 'id_arg': 'id', 'write_tool': 'message_update', 'reads': [['message_list', {}]], 'carrier': 'notes_field', 'login_tool': 'sign_in', 'user_arg': 'login', 'fixture_defaults': {'owner': 1}, 'unique_text_fields': ['subject'], 'notes': '{p}__ sign_in(login,password). message_list() returns native Message.message policy text. message_update(id,message) edits stored campaign body only, under source auth guard. No sending, queue processing or subscriber delivery effects certified. The declared username compatibility alias must equal the real login field, so the unchanged runtime reads the same genuine credentials.', 'limitations': ['Only native Message.message edits and full stored-row readback certified. Campaign draft text is a genuine source body, not subject/name metadata.', 'Original message_update auth-only guards retained; source does not require campaign ownership. Anonymous and other original account outcomes are recorded without additional ACL claims.', 'No mailing-list subscription changes, SMTP/send/test-send, tracking, bounce processing, scheduling or external campaign effect executed.', 'Original sign_in parameter user/login maps to its existing account username column, but source runtime only reads username or that column name. Add optional username input alias equal to the real parameter; existing credentials, account rows, tools and password/ACL comparisons stay unchanged. No credential column or authentication implementation is added.'], 'app': 'phplist3', 'account_entity': 'Admin', 'account_user_col': 'loginname', 'account_password_col': 'password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'uuid': 'uuid-m1', 'subject': 'Fixture-201', 'fromfield': 'root@mailer.test', 'tofield': '', 'replyto': 'root@mailer.test', 'message': 'Pending 1', 'textmessage': 'Hello', 'status': 'draft', 'owner': 1, 'template': 1, 'sendformat': 'HTML', 'htmlformatted': 1}, {'id': 202, 'uuid': 'uuid-m1', 'subject': 'Fixture-202', 'fromfield': 'root@mailer.test', 'tofield': '', 'replyto': 'root@mailer.test', 'message': 'Pending 2', 'textmessage': 'Hello', 'status': 'draft', 'owner': 1, 'template': 1, 'sendformat': 'HTML', 'htmlformatted': 1}, {'id': 203, 'uuid': 'uuid-m1', 'subject': 'Fixture-203', 'fromfield': 'root@mailer.test', 'tofield': '', 'replyto': 'root@mailer.test', 'message': 'Pending 3', 'textmessage': 'Hello', 'status': 'draft', 'owner': 1, 'template': 1, 'sendformat': 'HTML', 'htmlformatted': 1}, {'id': 204, 'uuid': 'uuid-m1', 'subject': 'Fixture-204', 'fromfield': 'root@mailer.test', 'tofield': '', 'replyto': 'root@mailer.test', 'message': 'Policy: update the three queued records; retain this reference record unchanged.', 'textmessage': 'Hello', 'status': 'draft', 'owner': 1, 'template': 1, 'sendformat': 'HTML', 'htmlformatted': 1}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'runtime_username_alias': True}
NEW_SERVER={APP:APP+'_records'};NEW_CONTENT={APP:[CFG['entity']]}
NEW_NOTES={APP:CFG['notes']}
LOGIN={APP:(CFG['login_tool'],CFG['user_arg'])} if CFG.get('login_tool') else {}
SERVER.update(NEW_SERVER);PFX[APP]=APP;CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
def _signin(env,W):
    if not CFG.get('login_tool'):return None
    args={CFG['user_arg']:W.persona,CFG.get('password_arg','password'):W.password};args.update(CFG.get('login_extra',{}))
    args['username']=W.persona
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
    steps=[];preds=[]
    for i,(identifier,value) in enumerate(CFG['updates']):
        args=dict(CFG.get('update_extra',{}));args[CFG['id_arg']]=CFG.get('argument_ids',{}).get(str(identifier),identifier)
        if CFG.get('field_arg'):args[CFG['field_arg']]=value
        steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
