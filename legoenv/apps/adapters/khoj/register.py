"""Source-bound khoj adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='khoj';NEW_SERVER={APP:'conversation_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['KhojUser', 'Agent', 'ClientApplication']]}
NEW_NOTES={APP:'{p}__ request_login_code(email,email_verification_code=<chosen six-digit code>) is original native auth preparation; then sign_in(email,email_verification_code=<same code>). Base verification code remains unset. content_getfile(file_name=policy.md) returns FileObject.raw_text policy. chat_createsession() inserts blank local Conversation, chat_settitle(conversation_id,title), chat_clearhistory(conversation_id) edit/delete own metadata. No model, indexing, embeddings, generated chat, email delivery or scheduler execution.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='khoj';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'request_login_code'),{'email':self.persona,'email_verification_code':'123456'}).get('ok');assert env.call(NS(APP,'sign_in'),{'email':self.persona,'email_verification_code':'123456'}).get('ok')
    for t,args in [('content_getfile', {'file_name': 'policy.md'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Conversation',[{'id':101,'user_id':1,'title':'Operations','conversation_log':[]},{'id':102,'user_id':1,'title':'Review','conversation_log':[]},{'id':103,'user_id':2,'title':'Reference','conversation_log':[]}])
    records(W,'FileObject',[{'id': 201, 'file_name': 'policy.md', 'raw_text': 'Policy: rename conversation101 to Approved and102 to Reviewed. Create a new empty conversation. Keep reference file unchanged.', 'user_id': 1}, {'id': 202, 'file_name': 'review.md', 'raw_text': 'Pending review.', 'user_id': 1}, {'id': 203, 'file_name': 'reference.md', 'raw_text': 'Retain reference file.', 'user_id': 1}])
    steps=[('__APP__', 'chat_settitle', {'conversation_id': 101, 'title': 'Approved'}), ('__APP__', 'chat_settitle', {'conversation_id': 102, 'title': 'Reviewed'}), ('__APP__', 'chat_createsession', {})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Conversation'),AND(F('id','eq',101),F('title','eq','Approved')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Conversation'),AND(F('id','eq',102),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Conversation'),AND(F('id','eq',104),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'FileObject'),AND(F('id','eq',203),F('raw_text','eq','Retain reference file.')))),True))
    steps=[lambda e:e.call(NS(APP,'request_login_code'),{'email':W.persona,'email_verification_code':'123456'}),lambda e:e.call(NS(APP,'sign_in'),{'email':W.persona,'email_verification_code':'123456'})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
