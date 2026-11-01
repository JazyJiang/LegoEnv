"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='linkwarden'
CFG={'order': 117, 'entity': 'Collection', 'pk': 'id', 'field': 'description', 'field_arg': 'description', 'id_arg': 'id', 'write_tool': 'collection_update', 'update_extra': {'name': 'Reviewed collection'}, 'reads': [['collection_read', {'id': 204}]], 'carrier': 'notes_field', 'login_tool': 'sign_in', 'user_arg': 'email', 'fixture_defaults': {'ownerId': 1}, 'notes': '{p}__ sign_in(email,password). collection_read(id) exposes native Collection.description policy; collection_update(id,name,description) updates stored metadata. Source owner/existing-user precondition alternatives are preserved and empirically bounded. No archival/browser/network effects claimed.', 'limitations': ['Only Collection.description stored edits/readback certified. No web-page archive capture, browser fetch, extraction, remote bookmarking, file/image or tag propagation executed.', 'Original source collection_update guard is existing User OR addressed owner rather than a conjunction; unrelated signed-in source accounts may therefore write. Actual peer outcome is reported without claiming stronger ownership enforcement.', 'Native collection_read retains its owner/member/visibility behavior; original User and UsersAndCollections scaffolding is unchanged.'], 'app': 'linkwarden', 'account_entity': 'User', 'account_user_col': 'email', 'account_password_col': 'password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'name': 'Research', 'description': 'Pending 1', 'icon': None, 'iconWeight': None, 'color': '#0ea5e9', 'parentId': None, 'isPublic': True, 'ownerId': 1, 'createdById': 1, 'createdAt': '2025-01-05T00:00:00Z', 'updatedAt': '2025-01-05T00:00:00Z'}, {'id': 202, 'name': 'Research', 'description': 'Pending 2', 'icon': None, 'iconWeight': None, 'color': '#0ea5e9', 'parentId': None, 'isPublic': True, 'ownerId': 1, 'createdById': 1, 'createdAt': '2025-01-05T00:00:00Z', 'updatedAt': '2025-01-05T00:00:00Z'}, {'id': 203, 'name': 'Research', 'description': 'Pending 3', 'icon': None, 'iconWeight': None, 'color': '#0ea5e9', 'parentId': None, 'isPublic': True, 'ownerId': 1, 'createdById': 1, 'createdAt': '2025-01-05T00:00:00Z', 'updatedAt': '2025-01-05T00:00:00Z'}, {'id': 204, 'name': 'Research', 'description': 'Policy: update the three queued records; retain this reference record unchanged.', 'icon': None, 'iconWeight': None, 'color': '#0ea5e9', 'parentId': None, 'isPublic': True, 'ownerId': 1, 'createdById': 1, 'createdAt': '2025-01-05T00:00:00Z', 'updatedAt': '2025-01-05T00:00:00Z'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
