"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='invoiceninja'
CFG={'order': 102, 'entity': 'Invoice', 'pk': 'id', 'field': 'public_notes', 'field_arg': 'public_notes', 'id_arg': 'invoice', 'write_tool': 'update_invoice', 'update_extra': {'company_id': 1}, 'reads': [['get_invoice_pdf', {'invoice': 204, 'action': 'pdf', 'company_id': 1}]], 'carrier': 'notes_field', 'login_tool': 'login', 'user_arg': 'email', 'unique_text_fields': ['number'], 'fixture_defaults': {'company_id': 1, 'user_id': 1, 'client_id': 1}, 'notes': '{p}__ login(email,password). update_invoice(invoice,company_id,public_notes) edits native invoice text under original CompanyUser admin/owner guards. get_invoice_pdf returns a native Invoice row in this executor, not PDF bytes; public_notes is readable there. No accounting/transport effect is certified.', 'limitations': ['Only native Invoice.public_notes updates and source Invoice row reads certified; get_invoice_pdf is a row executor, not actual PDF generation/download.', 'Original CompanyUser admin/owner preconditions and tenant argument preserved. Actual anonymous and other-source-account probes report the boundary without adding row ownership guards.', 'No invoice sending, payment processing, gateway calls, ledger posting or email delivery claimed.'], 'app': 'invoiceninja', 'account_entity': 'User', 'account_user_col': 'email', 'account_password_col': 'password', 'fixture_rows': [{'id': 201, 'company_id': 1, 'client_id': 1, 'user_id': 1, 'status_id': 1, 'discount': 0, 'is_amount_discount': 0, 'amount': 150.0, 'balance': 150.0, 'paid_to_date': 0, 'total_taxes': 0, 'tax_rate1': 0, 'tax_rate2': 0, 'tax_rate3': 0, 'uses_inclusive_taxes': 0, 'auto_bill_enabled': 0, 'auto_bill_tries': 0, 'is_proforma': 0, 'exchange_rate': 1.0, 'gateway_fee': 0, 'custom_surcharge_tax1': 0, 'custom_surcharge_tax2': 0, 'custom_surcharge_tax3': 0, 'custom_surcharge_tax4': 0, 'is_deleted': 0, 'number': 'Fixture-201', 'line_items': [{'product_key': 'CONSULT', 'qty': 1, 'cost': 150.0}], 'public_notes': 'Pending 1'}, {'id': 202, 'company_id': 1, 'client_id': 1, 'user_id': 1, 'status_id': 1, 'discount': 0, 'is_amount_discount': 0, 'amount': 150.0, 'balance': 150.0, 'paid_to_date': 0, 'total_taxes': 0, 'tax_rate1': 0, 'tax_rate2': 0, 'tax_rate3': 0, 'uses_inclusive_taxes': 0, 'auto_bill_enabled': 0, 'auto_bill_tries': 0, 'is_proforma': 0, 'exchange_rate': 1.0, 'gateway_fee': 0, 'custom_surcharge_tax1': 0, 'custom_surcharge_tax2': 0, 'custom_surcharge_tax3': 0, 'custom_surcharge_tax4': 0, 'is_deleted': 0, 'number': 'Fixture-202', 'line_items': [{'product_key': 'CONSULT', 'qty': 1, 'cost': 150.0}], 'public_notes': 'Pending 2'}, {'id': 203, 'company_id': 1, 'client_id': 1, 'user_id': 1, 'status_id': 1, 'discount': 0, 'is_amount_discount': 0, 'amount': 150.0, 'balance': 150.0, 'paid_to_date': 0, 'total_taxes': 0, 'tax_rate1': 0, 'tax_rate2': 0, 'tax_rate3': 0, 'uses_inclusive_taxes': 0, 'auto_bill_enabled': 0, 'auto_bill_tries': 0, 'is_proforma': 0, 'exchange_rate': 1.0, 'gateway_fee': 0, 'custom_surcharge_tax1': 0, 'custom_surcharge_tax2': 0, 'custom_surcharge_tax3': 0, 'custom_surcharge_tax4': 0, 'is_deleted': 0, 'number': 'Fixture-203', 'line_items': [{'product_key': 'CONSULT', 'qty': 1, 'cost': 150.0}], 'public_notes': 'Pending 3'}, {'id': 204, 'company_id': 1, 'client_id': 1, 'user_id': 1, 'status_id': 1, 'discount': 0, 'is_amount_discount': 0, 'amount': 150.0, 'balance': 150.0, 'paid_to_date': 0, 'total_taxes': 0, 'tax_rate1': 0, 'tax_rate2': 0, 'tax_rate3': 0, 'uses_inclusive_taxes': 0, 'auto_bill_enabled': 0, 'auto_bill_tries': 0, 'is_proforma': 0, 'exchange_rate': 1.0, 'gateway_fee': 0, 'custom_surcharge_tax1': 0, 'custom_surcharge_tax2': 0, 'custom_surcharge_tax3': 0, 'custom_surcharge_tax4': 0, 'is_deleted': 0, 'number': 'Fixture-204', 'line_items': [{'product_key': 'CONSULT', 'qty': 1, 'cost': 150.0}], 'public_notes': 'Policy: update the three queued records; retain this reference record unchanged.'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.']}
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
