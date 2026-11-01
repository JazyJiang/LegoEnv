"""Source-bound saleor adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='saleor';NEW_SERVER={APP:'saleor_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'ProductType', 'Category', 'TaxClass']]}
NEW_NOTES={APP:'{p}__ account_login(email,password). get_product(id=201) reads genuine source Product.description_plaintext. product_create(name,slug,product_type,category,tax_class), product_update(id,name,slug), product_delete(id) certify local metadata. description_plaintext is read-only in original panel; no write or JSON text flattening invented. Original staff guard retained.'}
LOGIN={APP:('account_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='saleor';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'account_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('get_product', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Product',[{'id': 201, 'name': 'Policy', 'slug': 'policy', 'product_type': 1, 'category': 1, 'tax_class': 1, 'description': {}, 'description_plaintext': 'Policy: update product202 name to Reviewed and slug reviewed. Create Approved product. Keep Reference unchanged.'}, {'id': 202, 'name': 'Pending', 'slug': 'review', 'product_type': 1, 'category': 1, 'tax_class': 1, 'description': {}, 'description_plaintext': 'Pending review.'}, {'id': 203, 'name': 'Reference', 'slug': 'reference', 'product_type': 1, 'category': 1, 'tax_class': 1, 'description': {}, 'description_plaintext': 'Retain reference product.'}])
    steps=[('__APP__', 'product_update', {'id': 202, 'name': 'Reviewed', 'slug': 'reviewed'}), ('__APP__', 'product_create', {'name': 'Approved', 'slug': 'approved', 'product_type': 1, 'category': 1, 'tax_class': 1})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('id','eq',202),F('slug','eq','reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('name','eq','Approved'),F('slug','eq','approved')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('id','eq',203),F('description_plaintext','eq','Retain reference product.')))),True))
    return steps,preds
