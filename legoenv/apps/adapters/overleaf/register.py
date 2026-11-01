"""Source-bound overleaf adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='overleaf';NEW_SERVER={APP:'overleaf_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,hashedPassword). project_getprojectinfo(project_id) returns Project.description policy. project_rename(projectId,newProjectName) and project_updatesettings(projectId,compiler,name) change genuine scalar metadata; project_archive(projectId) stores source scalar caller id in archived. Native document-content read returns Project without document body, project_create projectName alias is not implemented. No compilation, document editing or collaboration delivery.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='overleaf';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'hashedPassword':self.password}).get('ok')
    for t,args in [('project_getprojectinfo', {'project_id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Project',[{'id': 201, '_id': 201, 'name': 'Policy', 'description': 'Policy: rename project202 to Reviewed, select xelatex compiler, archive project202. Keep Reference unchanged.', 'owner_ref': 1, 'compiler': 'pdflatex', 'archived': [], 'trashed': []}, {'id': 202, '_id': 202, 'name': 'Pending', 'description': 'Pending review.', 'owner_ref': 1, 'compiler': 'pdflatex', 'archived': [], 'trashed': []}, {'id': 203, '_id': 203, 'name': 'Reference', 'description': 'Retain reference project.', 'owner_ref': 1, 'compiler': 'pdflatex', 'archived': [], 'trashed': []}])
    steps=[('__APP__', 'project_rename', {'projectId': 202, 'newProjectName': 'Reviewed'}), ('__APP__', 'project_updatesettings', {'projectId': 202, 'compiler': 'xelatex'}), ('__APP__', 'project_archive', {'projectId': 202})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Project'),AND(F('_id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Project'),AND(F('_id','eq',202),F('compiler','eq','xelatex')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Project'),AND(F('_id','eq',202),F('archived','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Project'),AND(F('_id','eq',203),F('description','eq','Retain reference project.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'email':W.persona,'hashedPassword':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
