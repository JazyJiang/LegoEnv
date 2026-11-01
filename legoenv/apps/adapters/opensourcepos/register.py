"""Source-bound opensourcepos adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='opensourcepos';NEW_SERVER={APP:'opensourcepos_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Employee', 'Person', 'Grant', 'Permission', 'Module', 'TaxCategory', 'Supplier', 'Expense', 'ExpenseCategory']]}
NEW_NOTES={APP:'{p}__ employee_login(username,password) uses genuine Employee/Person identity. item_search() reads Item.description policy under original items grants. item_update_item_number(item_id,item_number) updates actual SKU only. No expenses grant exists, so expense read/write remain unavailable. No fake grants, sales, inventory, receipts, payment or real POS operations.'}
LOGIN={APP:('employee_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='opensourcepos';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'employee_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('item_search', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Item',[{'id': 201, 'item_id': 201, 'name': 'Policy', 'item_number': 'POLICY', 'description': 'Policy: update item202 SKU REVIEWED-202, item203 REVIEWED-203 and item204 REVIEWED-204. Keep Reference unchanged.', 'category': 'Operations', 'cost_price': 1, 'unit_price': 2, 'deleted': 0}, {'id': 202, 'item_id': 202, 'name': 'First', 'item_number': 'PENDING-202', 'description': 'Review first item.', 'category': 'Operations', 'cost_price': 1, 'unit_price': 2, 'deleted': 0}, {'id': 203, 'item_id': 203, 'name': 'Second', 'item_number': 'PENDING-203', 'description': 'Review second item.', 'category': 'Operations', 'cost_price': 1, 'unit_price': 2, 'deleted': 0}, {'id': 204, 'item_id': 204, 'name': 'Third', 'item_number': 'PENDING-204', 'description': 'Review third item.', 'category': 'Operations', 'cost_price': 1, 'unit_price': 2, 'deleted': 0}, {'id': 205, 'item_id': 205, 'name': 'Reference', 'item_number': 'REFERENCE', 'description': 'Retain reference item.', 'category': 'Operations', 'cost_price': 1, 'unit_price': 2, 'deleted': 0}])
    steps=[('__APP__', 'item_update_item_number', {'item_id': 202, 'item_number': 'REVIEWED-202'}), ('__APP__', 'item_update_item_number', {'item_id': 203, 'item_number': 'REVIEWED-203'}), ('__APP__', 'item_update_item_number', {'item_id': 204, 'item_number': 'REVIEWED-204'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Item'),AND(F('item_id','eq',202),F('item_number','eq','REVIEWED-202')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Item'),AND(F('item_id','eq',203),F('item_number','eq','REVIEWED-203')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Item'),AND(F('item_id','eq',204),F('item_number','eq','REVIEWED-204')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Item'),AND(F('item_id','eq',205),F('description','eq','Retain reference item.'),F('item_number','eq','REFERENCE')))),True))
    return steps,preds
