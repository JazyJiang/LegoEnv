'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound registration; no invented tool or authentication implementation.'
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='seerr'
CFG={'order': 113, 'entity': 'IssueComment', 'pk': 'id', 'field': 'message', 'field_arg': 'message', 'id_arg': 'commentId', 'write_tool': 'issuecomment_update', 'reads': [['issue_read', {'issueId': 1}]], 'login_tool': 'auth_loginlocal', 'user_arg': 'email', 'fixture_defaults': {'user_id': 1}, 'blocked_reason': 'BLOCKED_MISSING_READABLE_POLICY_CARRIER', 'missing_tools': ['Native read/list tool for IssueComment.message'], 'notes': '{p}__ auth_loginlocal(email,password). issuecomment_update(commentId,message) edits a stored comment under its original author guard. issue_read(issueId) returns Issue metadata without comment join; no readable comment policy carrier is invented. Full onboarding blocked.', 'limitations': ['Complete onboarding blocked: narrative IssueComment.message has no source read/list operation; issue_read returns its Issue row and does not join comments. Issue metadata/configuration/name fields are not substituted for policy.', 'Only independent IssueComment.message local edits under original author check certified. Original User permissions and Issue ownership scaffold retained.', 'No movie/TV downloads, media server changes, notification delivery, playback, remote auth or external effects claimed.'], 'app': 'seerr', 'account_entity': 'User', 'account_user_col': 'email', 'account_password_col': 'password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'user_id': 1, 'issue_id': 1, 'message': 'Pending 1'}, {'id': 202, 'user_id': 1, 'issue_id': 1, 'message': 'Pending 2'}, {'id': 203, 'user_id': 1, 'issue_id': 1, 'message': 'Pending 3'}, {'id': 204, 'user_id': 1, 'issue_id': 1, 'message': 'Reference retained.'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Reference retained.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
        args=dict(CFG.get('update_extra',{}));args[CFG['id_arg']]=CFG.get('argument_ids',{}).get(str(identifier),identifier)
        if CFG.get('field_arg'):args[CFG['field_arg']]=value
        steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
