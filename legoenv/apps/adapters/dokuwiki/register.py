"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='dokuwiki'
CFG={'order': 111, 'entity': 'PluginConfig', 'pk': 'id', 'lookup_field': 'plugin', 'missing_argument': 'missing-plugin-fixture', 'field': 'enabled', 'field_arg': 'enabled', 'id_arg': 'plugin', 'write_tool': 'pluginconfig_set', 'kind': 'update_record', 'initial_value': False, 'updates': [[201, True], [202, True], [203, True]], 'integer_alias_entities': ['PluginConfig'], 'unique_text_fields': ['plugin'], 'reads': [['page_read', {'id': 'start'}]], 'login_tool': 'sign_in', 'user_arg': 'user', 'password_arg': 'pass', 'exec_binding_fixes': [{'tool': 'page_read', 'path': ['input_schema', 'id', 'type'], 'value': 'text', 'reason': 'Page.id is the source textual wiki business key; preserve its text argument instead of applying opaque-ID integer normalization.', 'source_evidence': ['entities.Page.columns.id.type=text', 'exec_spec.lookup_by.id=$arg.id']}], 'notes': '{p}__ sign_in(user,pass). page_read(id) exposes native wiki Page.content with original ACL guards. pluginconfig_set(plugin,enabled) only toggles local PluginConfig metadata; actual plugin loading/file/config persistence is not claimed. Plugin business keys remain text. The declared username compatibility alias must equal the real login field, so the unchanged runtime reads the same genuine credentials.', 'limitations': ['Only PluginConfig.enabled stored flags and native Page.content readback certified; no plugin activation, disk writes, git/history/rendering/media or remote XML-RPC effects executed.', 'Original source plugin guard is superuser-config OR addressed-plugin-exists; signed-in nonadmin may pass the second alternative. Exact source gap and observed peer outcomes are preserved, not replaced with an invented conjunction.', 'Page.id and plugin text business keys preserved; integer id is only an internal alias for PluginConfig predicate targeting. Native password argument pass is retained via original dklib callable support.', 'Original sign_in parameter user/login maps to its existing account username column, but source runtime only reads username or that column name. Add optional username input alias equal to the real parameter; existing credentials, account rows, tools and password/ACL comparisons stay unchanged. No credential column or authentication implementation is added.'], 'app': 'dokuwiki', 'account_entity': 'User', 'account_user_col': 'login', 'account_password_col': 'pass', 'argument_ids': {'201': 'Fixture-201', '202': 'Fixture-202', '203': 'Fixture-203', '204': 'Fixture-204'}, 'fixture_rows': [{'plugin': 'Fixture-201', 'enabled': False, 'id': 201}, {'plugin': 'Fixture-202', 'enabled': False, 'id': 202}, {'plugin': 'Fixture-203', 'enabled': False, 'id': 203}, {'plugin': 'Fixture-204', 'enabled': False, 'id': 204}], 'protected': [204, False], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'policy_page_id': 'start', 'carrier': 'notes_field', 'runtime_username_alias': True}
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
    next(r for r in W.spec[APP]['seed_state']['Page'] if r['id']==CFG['policy_page_id'])['content']=CFG['policy_text']
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
