"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='hyperswitch'
CFG={'app': 'hyperswitch', 'order': 115, 'entity': 'Customer', 'pk': 'id', 'lookup_field': 'customer_id', 'missing_argument': 'missing-customer-fixture', 'field': 'description', 'field_arg': 'description', 'id_arg': 'customer_id', 'write_tool': 'customer_update', 'integer_alias_entities': ['Customer'], 'unique_text_fields': ['customer_id'], 'reads': [['customer_retrieve', {'customer_id': 'Fixture-204'}]], 'carrier': 'notes_field', 'login_tool': 'user_login', 'user_arg': 'email', 'notes': '{p}__ user_login(email,password). customer_retrieve(customer_id) reads native Customer.description; customer_update(customer_id,description) edits that stored text. Customer/merchant business keys stay text. Source Customer operations have no auth/merchant-scoping guards beyond id existence; do not infer tenant isolation or actual payment processing.', 'limitations': ['Only native Customer.description edits/readback certified. Original customer_id and merchant_id textual composite business keys preserved; id is a separate internal integer alias for contract targeting.', 'Source Customer retrieve/update only check customer id existence and omit authenticated tenant/merchant guard. Anonymous and other-source-account outcomes are actually recorded; no payment/security/merchant authorization guarantee added.', 'No payment, refund, capture, connector gateway call, PII encryption, webhook, API-key authentication or remote effect claimed. Existing source User/role/merchant scaffolding remains unchanged.'], 'account_entity': 'User', 'account_user_col': 'email', 'account_password_col': 'password', 'argument_ids': {'201': 'Fixture-201', '202': 'Fixture-202', '203': 'Fixture-203', '204': 'Fixture-204'}, 'fixture_rows': [{'customer_id': 'Fixture-201', 'merchant_id': 'mer_1', 'name': 'Priya Sharma', 'email': 'priya@example.com', 'phone': '+15551234', 'version': 'V2', 'created_at': '2026-01-01T00:00:00', 'modified_at': '2026-01-01T00:00:00', 'id': 201, 'description': 'Pending 1'}, {'customer_id': 'Fixture-202', 'merchant_id': 'mer_1', 'name': 'Priya Sharma', 'email': 'priya@example.com', 'phone': '+15551234', 'version': 'V2', 'created_at': '2026-01-01T00:00:00', 'modified_at': '2026-01-01T00:00:00', 'id': 202, 'description': 'Pending 2'}, {'customer_id': 'Fixture-203', 'merchant_id': 'mer_1', 'name': 'Priya Sharma', 'email': 'priya@example.com', 'phone': '+15551234', 'version': 'V2', 'created_at': '2026-01-01T00:00:00', 'modified_at': '2026-01-01T00:00:00', 'id': 203, 'description': 'Pending 3'}, {'customer_id': 'Fixture-204', 'merchant_id': 'mer_1', 'name': 'Priya Sharma', 'email': 'priya@example.com', 'phone': '+15551234', 'version': 'V2', 'created_at': '2026-01-01T00:00:00', 'modified_at': '2026-01-01T00:00:00', 'id': 204, 'description': 'Policy: update the three queued records; retain this reference record unchanged.'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
