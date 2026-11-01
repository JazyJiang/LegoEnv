"""Home Gallery event log; pushing actions does not apply Entry tags."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='home_gallery';NEW_SERVER={APP:'gallery_event_log'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name']!='User']}
NEW_NOTES={APP:('{p}__ is a gallery event log. sign_in(email,password) verifies User1. entry_search(q) reads descriptions, tags and metadata using substring filters; entry_read_tree(hash) fetches a known actual hash. Entry.description carries policy. user_event_push(targetIds,actions,id) appends a UserActionEvent. It does not apply addTag/removeTag to Entry.tags; no direct Entry edit/delete/upload exists. user_action_log_read() reads the log. Download/watch are generic action emits, not binary transfer or a live stream. Integer internal ids are used for onboarding; source hash remains a separate business key.')}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='home_gallery';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t in ['entry_search','user_action_log_read']:
        r=env.call(NS(APP,t),{});assert r.get('ok'),r;rep[APP+' '+t]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def entries(W,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault('Entry',[]).extend(rows)
    if src:W.bindings[NS(APP,'Entry')]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    entries(W,[{'id':101,'hash':'policy-hash','type':'image','description':'Policy: append three action-log records 201,202,203 for Entry102: review, approved and archived tags respectively. This logs requested actions only. Keep reference Entry103 description unchanged.','tags':[]},{'id':102,'hash':'review-hash','type':'image','description':'Review gallery entry.','tags':['pending']},{'id':103,'hash':'reference-hash','type':'image','description':'Retain this reference description.','tags':['reference']}])
    steps=[(APP,'user_event_push',{'id':i,'targetIds':[102],'actions':[{'action':'addTag','value':tag}]}) for i,tag in [(201,'review'),(202,'approved'),(203,'archived')]]
    preds=[(str(i),'Requested action event logged.',CNT(SEL(NS(APP,'UserActionEvent'),F('id','eq',i))),False) for i in [201,202,203]]+ [('reference','Reference description unchanged.',CNT(SEL(NS(APP,'Entry'),AND(F('id','eq',103),F('description','eq','Retain this reference description.')))),True)]
    return steps,preds
