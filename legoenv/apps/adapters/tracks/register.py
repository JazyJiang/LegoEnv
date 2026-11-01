"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='tracks'
CFG={'order': 120, 'entity': 'Todo', 'pk': 'id', 'field': 'notes', 'field_arg': 'notes', 'id_arg': 'id', 'write_tool': 'todo_update', 'reads': [['todo_search', {'search': 'Policy'}]], 'carrier': 'notes_field', 'login_tool': 'sign_in', 'user_arg': 'login', 'fixture_defaults': {'user_id': 1, 'state': 'active'}, 'notes': '{p}__ sign_in(login,password). todo_search(search) reads native Todo.notes; todo_update(id,notes) edits owned task notes with original User and owner checks. Source compiled password-column equality is used; no real password hash processing, recurrence engine or external action is claimed.', 'limitations': ['Only owned Todo.notes stored edits and note readback certified. No scheduler/recurrence, email, CSV artifact transfer, calendar or other external effects executed.', 'Original authenticated User plus Todo.user_id owner preconditions retained and independently probed against another original account. Context/project scaffold remains source-native.', 'Login follows source plaintext-equivalent compiled crypted_password comparison; this does not certify actual password cryptography or a live Tracks service.'], 'app': 'tracks', 'account_entity': 'User', 'account_user_col': 'login', 'account_password_col': 'crypted_password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'user_id': 1, 'context_id': 1, 'project_id': 1, 'description': 'Write the homepage copy', 'notes': 'Pending 1', 'state': 'active'}, {'id': 202, 'user_id': 1, 'context_id': 1, 'project_id': 1, 'description': 'Write the homepage copy', 'notes': 'Pending 2', 'state': 'active'}, {'id': 203, 'user_id': 1, 'context_id': 1, 'project_id': 1, 'description': 'Write the homepage copy', 'notes': 'Pending 3', 'state': 'active'}, {'id': 204, 'user_id': 1, 'context_id': 1, 'project_id': 1, 'description': 'Write the homepage copy', 'notes': 'Policy: update the three queued records; retain this reference record unchanged.', 'state': 'active'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
