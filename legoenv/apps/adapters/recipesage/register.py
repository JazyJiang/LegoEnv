"""Source-bound recipesage adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='recipesage';NEW_SERVER={APP:'recipesage_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_login(email,passwordHash) native panel. recipe_getrecipe(id=201) reads notes. recipe_createrecipe(title,ingredients,instructions,notes), recipe_updaterecipe(id,title,notes), recipe_deleterecipe(id) create/update/delete local recipe metadata. Owner predicates retained for writes; source direct recipe read is public.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='recipesage';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'passwordHash':self.password}).get('ok')
    for t,args in [('recipe_getrecipe', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Recipe',[{'id': 201, 'userId': 1, 'title': 'Policy', 'notes': 'Policy: update recipe202 notes to Reviewed and approved. and title Reviewed. Create Approved recipe metadata. Keep Reference unchanged.', 'ingredients': 'Metadata fixture.', 'instructions': 'Metadata fixture.'}, {'id': 202, 'userId': 1, 'title': 'Pending', 'notes': 'Pending review.', 'ingredients': 'Metadata fixture.', 'instructions': 'Metadata fixture.'}, {'id': 203, 'userId': 1, 'title': 'Reference', 'notes': 'Retain reference recipe.', 'ingredients': 'Metadata fixture.', 'instructions': 'Metadata fixture.'}])
    steps=[('__APP__', 'recipe_updaterecipe', {'id': 202, 'title': 'Reviewed', 'notes': 'Reviewed and approved.'}), ('__APP__', 'recipe_createrecipe', {'title': 'Approved', 'notes': 'Approved metadata.', 'ingredients': 'fixture', 'instructions': 'fixture'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Recipe'),AND(F('id','eq',202),F('notes','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Recipe'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Recipe'),AND(F('title','eq','Approved'),F('notes','eq','Approved metadata.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Recipe'),AND(F('id','eq',203),F('notes','eq','Retain reference recipe.')))),True))
    steps=[lambda e:e.call(NS(APP,'user_login'),{'email':W.persona,'passwordHash':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
