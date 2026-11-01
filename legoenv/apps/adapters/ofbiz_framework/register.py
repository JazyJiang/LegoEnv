"""Source-bound ofbiz_framework adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ofbiz_framework';NEW_SERVER={APP:'ofbiz_framework_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['UserLogin']]}
NEW_NOTES={APP:'{p}__ sign_in(userLoginId,currentPassword). findproductionruns() reads genuine WorkEffort.description. createworkeffort(workEffortName,description), updateworkeffort(workEffortId,workEffortName,description,priority), deleteworkeffort(workEffortId) are local scalar record effects. Delete/search are public in source; logged-in writes have no owner/role predicate.'}
LOGIN={APP:('sign_in','userLoginId')};SERVER.update(NEW_SERVER);PFX[APP]='ofbiz_framework';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'userLoginId':self.persona,'currentPassword':self.password}).get('ok')
    for t,args in [('findproductionruns', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'WorkEffort',[{'id': 201, 'workEffortId': 201, 'workEffortName': 'Policy', 'description': 'Policy: update work effort202 description to Reviewed and approved. and name Reviewed. Create Approved work effort. Keep Reference unchanged.', 'priority': 1}, {'id': 202, 'workEffortId': 202, 'workEffortName': 'Pending', 'description': 'Pending review.', 'priority': 1}, {'id': 203, 'workEffortId': 203, 'workEffortName': 'Reference', 'description': 'Retain reference work effort.', 'priority': 1}])
    steps=[('__APP__', 'updateworkeffort', {'workEffortId': 202, 'description': 'Reviewed and approved.', 'workEffortName': 'Reviewed'}), ('__APP__', 'createworkeffort', {'workEffortName': 'Approved', 'description': 'Approved effort.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'WorkEffort'),AND(F('workEffortId','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'WorkEffort'),AND(F('workEffortId','eq',202),F('workEffortName','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'WorkEffort'),AND(F('workEffortName','eq','Approved'),F('description','eq','Approved effort.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'WorkEffort'),AND(F('workEffortId','eq',203),F('description','eq','Retain reference work effort.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'userLoginId':W.persona,'currentPassword':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
