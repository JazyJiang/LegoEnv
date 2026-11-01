"""Source-bound recipes adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='recipes';NEW_SERVER={APP:'recipe_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Space', 'UserSpace', 'Household', 'MealType', 'Food', 'Unit']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password). recipe_list(query) and recipe_retrieve(pk) read Recipe.description policy. Source space equals actor id; provided User1/Space1 membership is aligned. recipe_create(name,description,private), recipe_update(pk,name,description), recipe_destroy(pk) write scalars. mealplan_create(title,recipe,meal_type,from_date), mealplan_update(pk,note), mealplan_destroy(pk) operate dated metadata only. shoppinglistentry_create(food,unit,amount,checked), shoppinglistentry_update(pk,amount,checked), shoppinglistentry_destroy(pk) operate rows. No nested ingredient/step persistence, automation, AI calls, grocery connector delivery or comprehensive tenant/owner ACL certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='recipes';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('recipe_list', {}), ('mealplan_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Recipe',[{'id':201,'name':'Review policy','description':'Policy: set recipe202 description Reviewed recipe.; create meal plan Approved dinner for recipe202/type1 on 2026-09-30; add shopping food1 amount2. Keep reference recipe203 description unchanged.','space':1,'created_by':1,'private':False},{'id':202,'name':'Review recipe','description':'Pending review.','space':1,'created_by':1,'private':False},{'id':203,'name':'Reference recipe','description':'Retain reference recipe description.','space':1,'created_by':1,'private':False}])
    steps=[(APP,'recipe_update',{'pk':202,'name':'Review recipe','description':'Reviewed recipe.'}),(APP,'mealplan_create',{'title':'Approved dinner','recipe':202,'meal_type':1,'from_date':'2026-09-30T18:00:00','servings':2}),(APP,'shoppinglistentry_create',{'food':1,'unit':1,'amount':2,'checked':False})]
    preds=[('recipe','Recipe description updated.',CNT(SEL(NS(APP,'Recipe'),AND(F('id','eq',202),F('description','eq','Reviewed recipe.')))),False),('meal','Meal-plan scalar record created.',CNT(SEL(NS(APP,'MealPlan'),AND(F('title','eq','Approved dinner'),F('recipe','eq',202)))),False),('shopping','Shopping item record created.',CNT(SEL(NS(APP,'ShoppingListEntry'),AND(F('food','eq',1),F('amount','eq',2)))),False),('reference','Reference recipe unchanged.',CNT(SEL(NS(APP,'Recipe'),AND(F('id','eq',203),F('description','eq','Retain reference recipe description.')))),True)]
    return steps,preds
