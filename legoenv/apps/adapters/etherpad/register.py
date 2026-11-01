'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound registration; no invented tool or authentication implementation.'
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='etherpad'
CFG={'order': 107, 'entity': 'Author', 'pk': 'id', 'field': 'erased', 'field_arg': None, 'id_arg': 'authorID', 'write_tool': 'author_anonymize', 'kind': 'update_record', 'initial_value': False, 'updates': [[201, True], [202, True], [203, True]], 'reads': [['author_getauthorname', {'authorID': 204}]], 'blocked_reason': 'BLOCKED_MISSING_SOURCE_AUTH', 'missing_tools': ['Source authentication/account/login interface'], 'notes': '{p}__ source has no authentication. author_getauthorname(authorID) and author_anonymize(authorID) operate local opaque author identities. Only Author.erased metadata under explicit integer identity adapter is certified. Pad business names, text/OT revisions, sockets and collaboration are not certified.', 'limitations': ['Full onboarding blocked: source has no account/password/login interface; no API-key/login substitute invented. Independent native metadata checks do not qualify the app.', 'Only local Author.erased flag changes under opaque author identity normalization certified. Original Pad.id textual business names remain unchanged; no pad content or policy shape is invented.', 'No collaborative editing, OT changeset processing, revision persistence, websocket traffic, physical author privacy erasure or external effects claimed.'], 'app': 'etherpad', 'fixture_rows': [{'id': 201, 'name': 'Tester', 'colorId': 1, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}, {'id': 202, 'name': 'Tester', 'colorId': 1, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}, {'id': 203, 'name': 'Tester', 'colorId': 1, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}, {'id': 204, 'name': 'Tester', 'colorId': 1, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}], 'protected': [204, False], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'base_author_scaffold': [{'id': 1, 'name': 'Tester', 'colorId': 1, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}, {'id': 2, 'name': 'Engineer', 'colorId': 2, 'timestamp': '2026-01-01T00:00:00', 'lastSeen': '2026-01-01T00:00:00', 'padIDs': '{}', 'erased': False, 'erasedAt': None}]}
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
    rows=copy.deepcopy(rows);assert all(isinstance(r['id'],int) for r in rows);W.seed(APP,entity,copy.deepcopy(CFG['base_author_scaffold'])+rows,src=src);return rows
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

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
