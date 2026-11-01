"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='stirling_pdf'
CFG={'order': 104, 'raw_app': 'stirling-pdf', 'entity': 'Folder', 'pk': 'folder_id', 'field': 'name', 'field_arg': 'name', 'id_arg': 'folderId', 'write_tool': 'folder_update', 'reads': [['folder_search', {}], ['workflowsession_read', {'sessionId': 'ws-1'}]], 'login_tool': 'user_login', 'user_arg': 'username', 'fixture_defaults': {'owner_id': 1}, 'missing_tools': [], 'notes': '{p}__ user_login(username,password). folder_update(folderId,name) and folder_search operate native owner-scoped folder metadata. workflowsession_read(sessionId) genuinely reads owner-scoped WorkflowSession.message text used for policy. No PDF bytes, signing or processing effects claimed.', 'limitations': ['Logical app stirling_pdf binds exact source stirling-pdf.spec.json; all 95 original tool names/count/order retained.', 'Only Folder.name metadata updates and genuine owner-scoped WorkflowSession.message readback certified. Source Folder owner guard is retained and other-account rejection is probed.', 'WorkflowSession.message is an existing native human-message field, read through original workflowsession_read and its owner guard. File names, labels, JSON config and PDF bytes are not substituted for narrative policy.', 'No actual PDF transformation, OCR, signing, artifact transfer, document rendering, workflow engine execution or external effect claimed.'], 'app': 'stirling_pdf', 'account_entity': 'User', 'account_user_col': 'username', 'account_password_col': 'password', 'fixture_rows': [{'folder_id': 201, 'owner_id': 1, 'parent_folder_id': None, 'name': 'Pending 1', 'color': None, 'icon': None, 'version': 0, 'created_at': '2026-01-01T00:00:00', 'updated_at': '2026-01-01T00:00:00', 'id': 201}, {'folder_id': 202, 'owner_id': 1, 'parent_folder_id': None, 'name': 'Pending 2', 'color': None, 'icon': None, 'version': 0, 'created_at': '2026-01-01T00:00:00', 'updated_at': '2026-01-01T00:00:00', 'id': 202}, {'folder_id': 203, 'owner_id': 1, 'parent_folder_id': None, 'name': 'Pending 3', 'color': None, 'icon': None, 'version': 0, 'created_at': '2026-01-01T00:00:00', 'updated_at': '2026-01-01T00:00:00', 'id': 203}, {'folder_id': 204, 'owner_id': 1, 'parent_folder_id': None, 'name': 'Reference retained.', 'color': None, 'icon': None, 'version': 0, 'created_at': '2026-01-01T00:00:00', 'updated_at': '2026-01-01T00:00:00', 'id': 204}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Reference retained.'], 'workflow_session_id': 'ws-1', 'policy_text': 'Policy: rename the three queued folders as directed; keep the reference folder unchanged.', 'carrier': 'notes_field'}
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
    next(r for r in W.spec[APP]['seed_state']['WorkflowSession'] if r['session_id']==CFG['workflow_session_id'])['message']=CFG['policy_text']
    steps=[];preds=[]
    for i,(identifier,value) in enumerate(CFG['updates']):
        args=dict(CFG.get('update_extra',{}));args.update({CFG['id_arg']:identifier,CFG['field_arg']:value});steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
