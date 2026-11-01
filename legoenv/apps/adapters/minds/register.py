'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-faithful no-auth registration; original onboarding remains blocked.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='minds';NEW_SERVER={APP:'project_skill_manager'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities']]}
NEW_NOTES={APP:('{p}__ is the source project/skill manager. This source has no authentication tool or account entity. '
    'project_list(q) and skill_list(q) list scalar rows with optional substring filters. Skill.instructions carries policy. '
    'project_create(name), project_update(project_id,name,is_active), project_delete(project_id) operate on project rows. '
    'skill_create(label,name,instructions), skill_update(skill_id,instructions,description), skill_delete(skill_id) operate on skill rows. '
    'No actual model invocation, scheduled execution, channel delivery, filesystem rename or binary transfer is implemented here. '
    'Original onboarding is blocked by missing source authentication; no fake login is registered.')}
SERVER.update(NEW_SERVER);PFX[APP]='minds';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
# Deliberately absent from packlib.LOGIN: no source authentication interface exists.
LOGIN={}
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for tool in ('project_list','skill_list'):
        result=env.call(NS(APP,tool),{})
        assert result.get('ok'),result
        rep[APP+' '+tool]=len(json.dumps(result,ensure_ascii=False,default=str))
    for row in env.state.get(NS(APP,'Skill'),[]):
        result=env.call(NS(APP,'skill_get'),{'skill_id':row['id']});assert result.get('ok'),result
        rep[APP+' skill_get '+str(row['id'])]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def projects(W,rows,src=None):return _append(W,'Project',[{'path':r['name'],'is_active':False,**r} for r in rows],src)
def skills(W,rows,src=None):return _append(W,'Skill',rows,src)
def smoke_seed(W):
    projects(W,[{'id':101,'name':'Operations review'},{'id':102,'name':'Reference project'},{'id':103,'name':'Support follow-up'}])
    skills(W,[{'id':201,'label':'Review policy','name':'review-policy','instructions':'Policy: rename the operations project to Reviewed operations and record approval in a new skill. Keep the reference project unchanged.'}])
    steps=[(APP,'project_update',{'project_id':101,'name':'Reviewed operations'}),(APP,'skill_create',{'label':'Approved review','name':'approved-review','instructions':'Operations review approved.'})]
    preds=[('renamed','Operations project renamed.',CNT(SEL(NS(APP,'Project'),AND(F('id','eq',101),F('name','eq','Reviewed operations')))),False),
        ('skill','Approval skill exists.',CNT(SEL(NS(APP,'Skill'),F('name','eq','approved-review'))),False),
        ('approval','Approval wording recorded.',CNT(SEL(NS(APP,'Skill'),AND(F('name','eq','approved-review'),F('instructions','eq','Operations review approved.')))),False),
        ('reference','Reference project stays unchanged.',CNT(SEL(NS(APP,'Project'),AND(F('id','eq',102),F('name','eq','Reference project')))),True)]
    return steps,preds
__all__=['NEW_SERVER','projects','skills','smoke_seed']

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
