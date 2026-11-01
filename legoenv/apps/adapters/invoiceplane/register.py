"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='invoiceplane'
CFG={'order': 114, 'entity': 'Invoice', 'pk': 'invoice_id', 'field': 'invoice_status_id', 'field_arg': None, 'id_arg': 'invoice_id', 'write_tool': 'invoice_generate_pdf', 'kind': 'record_status_change', 'initial_value': 1, 'updates': [[201, 2], [202, 2], [203, 2]], 'reads': [['invoice_view', {'invoice_id': 204}]], 'carrier': 'notes_field', 'carrier_field': 'invoice_terms', 'login_tool': 'sign_in', 'user_arg': 'user_email', 'password_arg': 'user_password', 'fixture_defaults': {'user_id': 1}, 'unique_text_fields': ['invoice_number'], 'notes': '{p}__ sign_in(user_email,user_password). invoice_view(invoice_id) reads native invoice_terms. invoice_generate_pdf(invoice_id) in this source executor only sets invoice_status_id=2; certification covers that local transition, not actual PDF generation or transport.', 'limitations': ['Only native invoice_status_id transition to 2 and invoice_terms readback certified. invoice_generate_pdf tool name does not establish a real PDF artifact: its executor writes status only.', 'Existing User administrator user_type 1 and client membership guards retained. Native user_password parameter is passed via unchanged dklib callable support; no fake password alias or user role invented.', 'No actual invoice PDF, SMTP mailing, payment gateway, tax/accounting reconciliation, artifact transfer or external effects executed.'], 'app': 'invoiceplane', 'account_entity': 'User', 'account_user_col': 'user_email', 'account_password_col': 'user_password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'invoice_id': 201, 'user_id': 1, 'client_id': 1, 'invoice_group_id': 1, 'invoice_status_id': 1, 'invoice_date_created': '2026-01-10T00:00:00', 'invoice_time_created': '00:00:00', 'invoice_date_due': '2026-02-10T00:00:00', 'invoice_number': 'Fixture-201', 'invoice_terms': 'Pending review.', 'invoice_url_key': 'inv-aaa', 'invoice_password': None, 'payment_method': 1, 'invoice_discount_amount': 0.0, 'invoice_discount_percent': 0.0, 'is_read_only': None, 'creditinvoice_parent_id': None, 'invoice_date_modified': '2026-10-20T09:00:00'}, {'id': 202, 'invoice_id': 202, 'user_id': 1, 'client_id': 1, 'invoice_group_id': 1, 'invoice_status_id': 1, 'invoice_date_created': '2026-01-10T00:00:00', 'invoice_time_created': '00:00:00', 'invoice_date_due': '2026-02-10T00:00:00', 'invoice_number': 'Fixture-202', 'invoice_terms': 'Pending review.', 'invoice_url_key': 'inv-aaa', 'invoice_password': None, 'payment_method': 1, 'invoice_discount_amount': 0.0, 'invoice_discount_percent': 0.0, 'is_read_only': None, 'creditinvoice_parent_id': None, 'invoice_date_modified': '2026-10-20T09:00:00'}, {'id': 203, 'invoice_id': 203, 'user_id': 1, 'client_id': 1, 'invoice_group_id': 1, 'invoice_status_id': 1, 'invoice_date_created': '2026-01-10T00:00:00', 'invoice_time_created': '00:00:00', 'invoice_date_due': '2026-02-10T00:00:00', 'invoice_number': 'Fixture-203', 'invoice_terms': 'Pending review.', 'invoice_url_key': 'inv-aaa', 'invoice_password': None, 'payment_method': 1, 'invoice_discount_amount': 0.0, 'invoice_discount_percent': 0.0, 'is_read_only': None, 'creditinvoice_parent_id': None, 'invoice_date_modified': '2026-10-20T09:00:00'}, {'id': 204, 'invoice_id': 204, 'user_id': 1, 'client_id': 1, 'invoice_group_id': 1, 'invoice_status_id': 1, 'invoice_date_created': '2026-01-10T00:00:00', 'invoice_time_created': '00:00:00', 'invoice_date_due': '2026-02-10T00:00:00', 'invoice_number': 'Fixture-204', 'invoice_terms': 'Policy: update the three queued records; retain this reference record unchanged.', 'invoice_url_key': 'inv-aaa', 'invoice_password': None, 'payment_method': 1, 'invoice_discount_amount': 0.0, 'invoice_discount_percent': 0.0, 'is_read_only': None, 'creditinvoice_parent_id': None, 'invoice_date_modified': '2026-10-20T09:00:00'}], 'protected': [204, 1], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.'}
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
