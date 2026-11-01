'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nERP source writes without fabricated login; original admission remains blocked.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='erpnext';NEW_SERVER={APP:'erp'}
CONFIG={'Company','User','ItemGroup','UOM','Currency','Country','PriceList','CustomerGroup','Territory','StockEntryType'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is the source ERP scalar interface. No authentication/login tool exists in this source; original onboarding is blocked. '
    'ERP business identities are name strings such as SO-101, not internal row ids. employee_get_children(parent) reads employees where reports_to equals parent; '
    'Employee.reason_for_leaving holds departure handling notes. salesorder_get_work_order_items(sales_order) reads matching child items. '
    'employee_create(first_name,company,date_of_birth,date_of_joining), item_create(item_code,item_group,stock_uom), warehouse_create(warehouse_name,company) create scalar rows. '
    'item_update(name,standard_rate,is_stock_item), employee_save(name,status,relieving_date), issue_set_status(name,status) update scalar fields. '
    'salesorder_submit(name) changes docstatus 0->1; salesorder_cancel(name) changes 1->2. These do not generate stock/accounting effects. '
    'warehouse_delete(name) deletes a row; its original stock guard is incomplete. Most ERP entities have no read interface. No complete finance, stock or permission workflow is certified.')}
SERVER.update(NEW_SERVER);PFX[APP]='erpnext';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
LOGIN={}
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for tool,args in [('employee_get_children',{'parent':'EMP-ROOT'}),('salesorder_get_work_order_items',{'sales_order':'SO-101'})]:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def employees(W,rows,src=None):return _append(W,'Employee',[{'status':'Active','company':'ACME','reports_to':'EMP-ROOT','date_of_birth':'1990-01-01','date_of_joining':'2020-01-01',**r} for r in rows],src)
def items(W,rows,src=None):return _append(W,'Item',[{'item_group':'Products','stock_uom':'Nos','standard_rate':10,**r} for r in rows],src)
def warehouses(W,rows,src=None):return _append(W,'Warehouse',[{'company':'ACME','is_group':False,**r} for r in rows],src)
def salesorders(W,rows,src=None):return _append(W,'SalesOrder',[{'docstatus':0,'status':'Draft','company':'ACME',**r} for r in rows],src)
def issues(W,rows,src=None):return _append(W,'Issue',[{'status':'Open',**r} for r in rows],src)
def smoke_seed(W):
    employees(W,[{'id':101,'name':'EMP-101','first_name':'Review employee','reason_for_leaving':'Policy: suspend the approved leave record, resolve the review issue, and keep the reference employee active.'},
        {'id':102,'name':'EMP-102','first_name':'Reference employee','reason_for_leaving':'Reference stays active.'}])
    issues(W,[{'id':201,'name':'ISS-201','subject':'Approved leave review'}])
    items(W,[{'id':301,'name':'ITEM-301','item_code':'ITEM-301','item_name':'Review item'}])
    salesorders(W,[{'id':401,'name':'SO-101'}])
    warehouses(W,[{'id':501,'name':'WAREHOUSE-501','warehouse_name':'Review warehouse'}])
    steps=[(APP,'employee_save',{'name':'EMP-101','status':'Suspended'}),(APP,'issue_set_status',{'name':'ISS-201','status':'Resolved'}),(APP,'salesorder_submit',{'name':'SO-101'})]
    preds=[('employee','Approved employee is suspended.',CNT(SEL(NS(APP,'Employee'),AND(F('name','eq','EMP-101'),F('status','eq','Suspended')))),False),
        ('issue','Review issue is resolved.',CNT(SEL(NS(APP,'Issue'),AND(F('name','eq','ISS-201'),F('status','eq','Resolved')))),False),
        ('order','Review order is submitted.',CNT(SEL(NS(APP,'SalesOrder'),AND(F('name','eq','SO-101'),F('docstatus','eq',1)))),False),
        ('reference','Reference employee remains active.',CNT(SEL(NS(APP,'Employee'),AND(F('name','eq','EMP-102'),F('status','eq','Active')))),True)]
    return steps,preds
__all__=['NEW_SERVER','employees','items','warehouses','salesorders','issues','smoke_seed']

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
