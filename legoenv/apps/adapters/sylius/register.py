"""Source-bound sylius adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='sylius';NEW_SERVER={APP:'sylius_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['AdminUser', 'ShopUser', 'Customer']]}
NEW_NOTES={APP:'{p}__ adminuser_login(email,password) genuine existing back-office identity opens admin realm. product_readbyslug(slug=policy) reads ProductTranslation.description. product_create(code,enabled), product_update(code,enabled), product_delete(code) edit local Product metadata; no translation body write exists or is invented. Source shopuser_login remains shop realm and cannot write admin catalog.'}
LOGIN={APP:('adminuser_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='sylius';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'adminuser_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('product_readbyslug', {'slug': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'ProductTranslation',[{'id': 201, 'locale': 'en_US', 'name': 'Policy', 'slug': 'policy', 'description': 'Policy: create approved1, approved2 and approved3 products with enabled true. Keep Reference unchanged.'}, {'id': 202, 'locale': 'en_US', 'name': 'Pending', 'slug': 'review', 'description': 'Pending review.'}, {'id': 203, 'locale': 'en_US', 'name': 'Reference', 'slug': 'reference', 'description': 'Retain reference translation.'}])
    steps=[('__APP__', 'product_create', {'code': 'approved1', 'enabled': True}), ('__APP__', 'product_create', {'code': 'approved2', 'enabled': True}), ('__APP__', 'product_create', {'code': 'approved3', 'enabled': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('code','eq','approved1'),F('enabled','eq',True)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('code','eq','approved2'),F('enabled','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Product'),AND(F('code','eq','approved3'),F('enabled','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'ProductTranslation'),AND(F('slug','eq','reference'),F('description','eq','Retain reference translation.')))),True))
    return steps,preds
