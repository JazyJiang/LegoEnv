"""Source-bound opnform adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='opnform';NEW_SERVER={APP:'opnform_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Workspace', 'UserWorkspace']]}
NEW_NOTES={APP:'{p}__ user_login(email,password). form_show(form=201) reads description with native workspace guard. form_store(workspace_id,title,slug,description) creates metadata; form_update(form,title,visibility) edits only native panel fields; form_destroy(form) sets deleted_at. Public fetch does not enforce public visibility in source.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='opnform';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('form_show', {'form': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Form',[{'id': 201, 'workspace_id': 1, 'creator_id': 1, 'title': 'Policy', 'slug': 'policy', 'description': 'Policy: set form202 title Reviewed and visibility closed. Create Approved form in workspace1. Keep Reference unchanged.', 'visibility': 'draft'}, {'id': 202, 'workspace_id': 1, 'creator_id': 1, 'title': 'Pending', 'slug': 'review', 'description': 'Pending review.', 'visibility': 'draft'}, {'id': 203, 'workspace_id': 1, 'creator_id': 1, 'title': 'Reference', 'slug': 'reference', 'description': 'Retain reference form.', 'visibility': 'draft'}])
    steps=[('__APP__', 'form_update', {'form': 202, 'title': 'Reviewed', 'visibility': 'closed'}), ('__APP__', 'form_store', {'workspace_id': 1, 'title': 'Approved', 'slug': 'approved', 'description': 'Approved form.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Form'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Form'),AND(F('id','eq',202),F('visibility','eq','closed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Form'),AND(F('slug','eq','approved'),F('description','eq','Approved form.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Form'),AND(F('id','eq',203),F('description','eq','Retain reference form.')))),True))
    return steps,preds
