"""Source-bound opencart adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='opencart';NEW_SERVER={APP:'opencart_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserGroup', 'Customer']]}
NEW_NOTES={APP:'{p}__ user_loginseed(username,password) opens original admin realm. taxclass_gettaxclasses() reads description. taxclass_addtaxclass(title,description) creates metadata; taxclass_deletetaxclass(tax_class_id) deletes. edittaxclass is TaxRule insertion and is not certified as parent update. Admin User/UserGroup status/group guards preserved.'}
LOGIN={APP:('user_loginseed','username')};SERVER.update(NEW_SERVER);PFX[APP]='opencart';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_loginseed'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('taxclass_gettaxclasses', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'TaxClass',[{'id': 201, 'tax_class_id': 201, 'title': 'Policy', 'description': 'Policy: create Approved1 Approved2 and Approved3 tax classes with approved descriptions. Keep Reference unchanged.'}, {'id': 202, 'tax_class_id': 202, 'title': 'Pending', 'description': 'Pending review.'}, {'id': 203, 'tax_class_id': 203, 'title': 'Reference', 'description': 'Retain reference tax class.'}])
    steps=[('__APP__', 'taxclass_addtaxclass', {'title': 'Approved1', 'description': 'Approved class1.'}), ('__APP__', 'taxclass_addtaxclass', {'title': 'Approved2', 'description': 'Approved class2.'}), ('__APP__', 'taxclass_addtaxclass', {'title': 'Approved3', 'description': 'Approved class3.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'TaxClass'),AND(F('title','eq','Approved1'),F('description','eq','Approved class1.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'TaxClass'),AND(F('title','eq','Approved2'),F('description','eq','Approved class2.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'TaxClass'),AND(F('title','eq','Approved3'),F('description','eq','Approved class3.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'TaxClass'),AND(F('tax_class_id','eq',203),F('description','eq','Retain reference tax class.')))),True))
    return steps,preds
