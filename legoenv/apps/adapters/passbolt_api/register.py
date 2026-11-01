"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='passbolt_api'
CFG={'order': 108, 'entity': 'Comment', 'pk': 'id', 'field': 'content', 'field_arg': 'content', 'id_arg': 'commentId', 'write_tool': 'update_comment', 'fixture_defaults': {'created_by': 1, 'modified_by': 1}, 'reads': [['list_comments', {'foreignModelName': 'Resource', 'foreignKey': 1}]], 'carrier': 'notes_field', 'login_tool': 'sign_in', 'user_arg': 'username', 'exec_binding_fixes': [{'tool': 'update_comment', 'path': ['exec_spec', 'row_key', 'id'], 'value': {'$arg': 'commentId'}, 'reason': 'Source declared commentId and original owner precondition both identify Comment.id; repair executor undeclared id alias to that same actual parameter, without changing guards.', 'source_evidence': ['input_schema.commentId', 'guards.preconditions[0][0].select.where.args[0].value.arg', '_evidence.locator:src/Controller/Comments/CommentsUpdateController.php']}], 'notes': '{p}__ sign_in(username,password). list_comments(foreignModelName,foreignKey) returns native comment text; update_comment(commentId,content) retains original author-only guard. Executor alias uses its declared commentId and same source guard key. No cryptographic secret access or key operation is certified.', 'limitations': ['Only Comment.content edits/readback under original author guard certified. No secret/password decryption, crypto, PGP signing or external delivery effects claimed.', 'Source update executor referred to undeclared id although input and owner precondition both use commentId; only that executor parameter alias repaired. No auth/owner precondition weakened.', 'list_comments source does not apply its advertised resource filter in executor; no resource-scoped comment listing guarantee claimed.'], 'app': 'passbolt_api', 'account_entity': 'User', 'account_user_col': 'username', 'account_password_col': 'password', 'fixture_rows': [{'id': 201, 'foreign_id': 1, 'foreign_model': 'Resource', 'content': 'Pending 1', 'created_by': 1, 'modified_by': 1}, {'id': 202, 'foreign_id': 1, 'foreign_model': 'Resource', 'content': 'Pending 2', 'created_by': 1, 'modified_by': 1}, {'id': 203, 'foreign_id': 1, 'foreign_model': 'Resource', 'content': 'Pending 3', 'created_by': 1, 'modified_by': 1}, {'id': 204, 'foreign_id': 1, 'foreign_model': 'Resource', 'content': 'Policy: update the three queued records; retain this reference record unchanged.', 'created_by': 1, 'modified_by': 1}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
