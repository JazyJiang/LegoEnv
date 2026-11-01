"""Source-bound lemmy adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='lemmy';NEW_SERVER={APP:'lemmy_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['LocalUser', 'Person']]}
NEW_NOTES={APP:'{p}__ localuser_login(email,password). tagline_list() reads native content. tagline_create(content), tagline_edit(id,content), tagline_delete(id) are local admin tagline CRUD. Source LocalUser admin predicate retained, ordinary local user denied all writes. No federation or remote site publication is performed.'}
LOGIN={APP:('localuser_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='lemmy';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'localuser_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('tagline_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Tagline',[{'id': 201, 'content': 'Policy: edit tagline202 content to Reviewed and approved. Create Approved tagline and Approved second tagline. Keep Reference unchanged.'}, {'id': 202, 'content': 'Pending review.'}, {'id': 203, 'content': 'Retain reference tagline.'}])
    steps=[('__APP__', 'tagline_edit', {'id': 202, 'content': 'Reviewed and approved.'}), ('__APP__', 'tagline_create', {'content': 'Approved tagline.'}), ('__APP__', 'tagline_create', {'content': 'Approved second tagline.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Tagline'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Tagline'),F('content','eq','Approved second tagline.'))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Tagline'),F('content','eq','Approved tagline.'))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Tagline'),AND(F('id','eq',203),F('content','eq','Retain reference tagline.')))),True))
    return steps,preds
