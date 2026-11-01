"""Source-bound coder adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='coder';NEW_SERVER={APP:'workspace_skill_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ signs in using user_login(email,password). userskill_list() and userskill_get(name) read your UserSkill.content markdown policy. userskill_create(name,content), userskill_update(name,content), userskill_delete(name) operate owned skill records. All other original tools remain, but no AI/MCP invocation, workspace provisioning, template build, credential transport, command execution or network effects are certified. Skill markdown is stored as text, not executed.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='coder';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('userskill_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'UserSkill',[{'id':201,'user_id':1,'name':'review-policy','content':'Policy: update review skill content to Reviewed and approved.; create approval skill with Review recorded. content. Keep reference skill content unchanged.'},{'id':202,'user_id':1,'name':'review','content':'Pending review.'},{'id':203,'user_id':1,'name':'reference','content':'Retain reference skill content.'}])
    steps=[(APP,'userskill_update',{'name':'review','content':'Reviewed and approved.'}),(APP,'userskill_create',{'name':'approval','content':'Review recorded.'})]
    preds=[('update','Own skill content updated.',CNT(SEL(NS(APP,'UserSkill'),AND(F('name','eq','review'),F('user_id','eq',1),F('content','eq','Reviewed and approved.')))),False),('create','Own approval skill created.',CNT(SEL(NS(APP,'UserSkill'),AND(F('name','eq','approval'),F('user_id','eq',1)))),False),('content','Approval wording persisted.',CNT(SEL(NS(APP,'UserSkill'),AND(F('name','eq','approval'),F('content','eq','Review recorded.')))),False),('reference','Reference markdown unchanged.',CNT(SEL(NS(APP,'UserSkill'),AND(F('name','eq','reference'),F('content','eq','Retain reference skill content.')))),True)]
    return steps,preds
