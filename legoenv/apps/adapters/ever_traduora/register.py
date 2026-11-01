"""Source-bound ever_traduora adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ever_traduora';NEW_SERVER={APP:'translation_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Plan', 'Locale', 'Project', 'ProjectUser', 'ProjectLocale']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(email,password), verified against encrypted_password. User1 is project1 admin; User2 viewer. list_terms(projectId) reads Term.context policy; list_translations(projectId,localeCode) reads actual locale-scoped translation rows. update_term(projectId,termId,context), set_translation(projectId,localeCode,termId,value) update scalars, resolving existing ProjectLocale FK. create_label(projectId,value,color), update_label(projectId,labelId,value,color), set_term_label(projectId,labelId,termId), unset_term_label and delete_label operate records. update_project(projectId,description) edits metadata. Source create_term/add_project_locale fanout is incomplete and not certified. No import/export execution, invitation delivery or comprehensive cross-target project validation certified.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='ever_traduora';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('list_terms', {'projectId': 1}), ('list_translations', {'projectId': 1, 'localeCode': 'en-US'}), ('list_labels', {'projectId': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Term',[{'id':201,'project_id':1,'value':'policy','context':'Policy: update term202 context Reviewed term context.; set term202/en-US translation Reviewed translation.; create Reviewed operations label. Keep reference term203 context unchanged.'},{'id':202,'project_id':1,'value':'review','context':'Pending term context.'},{'id':203,'project_id':1,'value':'reference','context':'Retain reference term context.'}]);records(W,'Translation',[{'id':301,'term_id':202,'project_locale_id':1,'value':'Pending translation.'}])
    steps=[(APP,'update_term',{'projectId':1,'termId':202,'context':'Reviewed term context.'}),(APP,'set_translation',{'projectId':1,'localeCode':'en-US','termId':202,'value':'Reviewed translation.'}),(APP,'create_label',{'projectId':1,'value':'Reviewed operations','color':'#337799'})]
    preds=[('term','Term context updated.',CNT(SEL(NS(APP,'Term'),AND(F('id','eq',202),F('context','eq','Reviewed term context.')))),False),('translation','Existing translation updated.',CNT(SEL(NS(APP,'Translation'),AND(F('term_id','eq',202),F('project_locale_id','eq',1),F('value','eq','Reviewed translation.')))),False),('label','Project label created.',CNT(SEL(NS(APP,'Label'),AND(F('project_id','eq',1),F('value','eq','Reviewed operations')))),False),('reference','Reference term context unchanged.',CNT(SEL(NS(APP,'Term'),AND(F('id','eq',203),F('context','eq','Retain reference term context.')))),True)]
    return steps,preds
