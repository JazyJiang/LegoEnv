"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='answer'
CFG={'order': 106, 'entity': 'Question', 'pk': 'id', 'field': 'status', 'field_arg': None, 'id_arg': 'id', 'write_tool': 'question_close', 'kind': 'record_status_change', 'initial_value': 1, 'updates': [[201, 2], [202, 2], [203, 2]], 'fixture_defaults': {'user_id': 1}, 'unique_text_fields': ['title'], 'reads': [['question_get', {'id': 204}]], 'carrier': 'notes_field', 'carrier_field': 'original_text', 'login_tool': 'sign_in', 'user_arg': 'e_mail', 'password_arg': 'pass', 'notes': '{p}__ sign_in(e_mail,pass). question_get(id) exposes native Question.original_text while status=1. question_close(id) sets native status=2; protected reference remains open. Source close guard checks open status but does not require authenticated ownership. The native password parameter is pass; callable smoke uses the unchanged original dklib supported hook.', 'limitations': ['Only native Question close status 1 to 2 and original_text readback certified. Original status guard retained; anonymous closure is possible in source and is actually reported.', 'Native login parameters e_mail/pass preserved; no renamed auth tool or fake password field. Supported original dklib callable steps record the real login, since its automatic tuple login assumes password.', 'No reputation, revision moderation, notification delivery or search-service effects claimed.'], 'app': 'answer', 'account_entity': 'User', 'account_user_col': 'e_mail', 'account_password_col': 'pass', 'fixture_rows': [{'id': 201, 'user_id': 1, 'title': 'Fixture-201', 'original_text': 'Pending review.', 'parsed_text': '<p>body</p>', 'status': 1, 'show': 1, 'pin': 1, 'answer_count': 1, 'view_count': 10}, {'id': 202, 'user_id': 1, 'title': 'Fixture-202', 'original_text': 'Pending review.', 'parsed_text': '<p>body</p>', 'status': 1, 'show': 1, 'pin': 1, 'answer_count': 1, 'view_count': 10}, {'id': 203, 'user_id': 1, 'title': 'Fixture-203', 'original_text': 'Pending review.', 'parsed_text': '<p>body</p>', 'status': 1, 'show': 1, 'pin': 1, 'answer_count': 1, 'view_count': 10}, {'id': 204, 'user_id': 1, 'title': 'Fixture-204', 'original_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'parsed_text': '<p>body</p>', 'status': 1, 'show': 1, 'pin': 1, 'answer_count': 1, 'view_count': 10}], 'protected': [204, 1], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
NEW_SERVER={APP:APP+'_records'};NEW_CONTENT={APP:[CFG['entity']]}
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
    steps=[];preds=[]
    for i,(identifier,value) in enumerate(CFG['updates']):
        args=dict(CFG.get('update_extra',{}));args[CFG['id_arg']]=identifier
        if CFG.get('field_arg'):args[CFG['field_arg']]=value
        steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
