"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='invoiceshelf'
CFG={'order': 119, 'entity': 'Item', 'pk': 'id', 'field': 'description', 'field_arg': 'description', 'id_arg': 'item', 'write_tool': 'item_update', 'reads': [['item_index', {}]], 'carrier': 'notes_field', 'login_tool': 'user_login', 'user_arg': 'email', 'login_extra': {'device_name': 'cpu-onboard'}, 'fixture_defaults': {'company_id': 1}, 'unique_text_fields': ['name'], 'exec_binding_fixes': [{'tool': 'item_index', 'path': ['exec_spec', 'scope', 'where', 'company_id'], 'value': {'$session': 'account_id'}, 'reason': 'Represent original literal session scope as its equivalent supported expression, keeping its original account_id mapping.', 'source_evidence': ['exec_spec.scope.where.company_id=$session.account_id']}], 'notes': '{p}__ user_login(email,password,device_name) uses existing staff credentials. item_index() reads native Item.description; item_update(item,description) changes stored catalog text. Source only checks existence of the authenticated User for updates; original account_id/company scope mapping is preserved, not strengthened.', 'limitations': ['Only Item.description stored updates/readback certified. No actual invoice/estimate generation, accounting posting, payment gateway, SMTP send, attachment bytes or external effect claimed.', 'Original item_update permits any existing authenticated source User; actual peer outcome is recorded, no company-role membership isolation added.', 'item_index literal company_id=$session.account_id becomes supported expression with exactly that mapping. Existing UserCompany/role/company scaffold retained; no new company-session identity is fabricated.'], 'app': 'invoiceshelf', 'account_entity': 'User', 'account_user_col': 'email', 'account_password_col': 'password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'name': 'Fixture-201', 'description': 'Pending 1', 'price': 150, 'company_id': 1, 'unit_id': 2, 'creator_id': 2}, {'id': 202, 'name': 'Fixture-202', 'description': 'Pending 2', 'price': 150, 'company_id': 1, 'unit_id': 2, 'creator_id': 2}, {'id': 203, 'name': 'Fixture-203', 'description': 'Pending 3', 'price': 150, 'company_id': 1, 'unit_id': 2, 'creator_id': 2}, {'id': 204, 'name': 'Fixture-204', 'description': 'Policy: update the three queued records; retain this reference record unchanged.', 'price': 150, 'company_id': 1, 'unit_id': 2, 'creator_id': 2}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
