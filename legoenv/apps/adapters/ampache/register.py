'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound registration; no invented tool or authentication implementation.'
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ampache'
CFG={'order': 105, 'entity': 'Broadcast', 'pk': 'id', 'field': 'description', 'field_arg': 'description', 'id_arg': 'id', 'write_tool': 'broadcast_update', 'reads': [['song_search', {'q': 'sample'}]], 'login_tool': 'sign_in', 'user_arg': 'username', 'fixture_defaults': {'user': 1}, 'blocked_reason': 'BLOCKED_MISSING_READABLE_POLICY_CARRIER', 'missing_tools': ['Native read tool for Broadcast.description or other narrative text'], 'notes': '{p}__ sign_in(username,password). broadcast_update(id,description) changes a native Broadcast row. Only song_search reads source Song metadata; it does not expose Broadcast.description. Full onboarding is blocked by missing readable narrative carrier.', 'limitations': ['Only Broadcast.description native stored-field updates certified. Source only reads Song file/title/mode/mbid/composer metadata, not Broadcast.description or other narrative fields. No song title/composer policy workaround.', 'Original broadcast_update authentication-only guard retained; no ownership isolation added.', 'Complete onboarding blocked by missing readable narrative policy carrier. No playback, streaming, media bytes, transcoding, recommendation or external delivery claimed.'], 'app': 'ampache', 'account_entity': 'User', 'account_user_col': 'username', 'account_password_col': 'password', 'fixture_rows': [{'id': 201, 'user': 1, 'name': 'Radio One', 'is_private': 0, 'song': 0, 'started': 0, 'listeners': 0, 'description': 'Pending 1'}, {'id': 202, 'user': 1, 'name': 'Radio One', 'is_private': 0, 'song': 0, 'started': 0, 'listeners': 0, 'description': 'Pending 2'}, {'id': 203, 'user': 1, 'name': 'Radio One', 'is_private': 0, 'song': 0, 'started': 0, 'listeners': 0, 'description': 'Pending 3'}, {'id': 204, 'user': 1, 'name': 'Radio One', 'is_private': 0, 'song': 0, 'started': 0, 'listeners': 0, 'description': 'Reference retained.'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Reference retained.']}
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
        args=dict(CFG.get('update_extra',{}));args.update({CFG['id_arg']:identifier,CFG['field_arg']:value});steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
