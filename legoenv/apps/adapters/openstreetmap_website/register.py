"""Source-bound openstreetmap_website adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='openstreetmap_website';NEW_SERVER={APP:'openstreetmap_website_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserRole', 'Language']]}
NEW_NOTES={APP:'{p}__ sign_in(email,pass_crypt). diaryentry_show(id=201,display_name=Ops) reads native body. diaryentry_create uses original diary_entry[title]/diary_entry[body] fields; diaryentry_update(id,diary_entry[title],diary_entry[body]) edits own metadata; diaryentry_hide(id) sets visible=false under existing admin/moderator role. Source show ignores supplied author and hidden visibility.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='openstreetmap_website';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'pass_crypt':self.password}).get('ok')
    for t,args in [('diaryentry_show', {'id': 201, 'display_name': 'Ops'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'DiaryEntry',[{'id': 201, 'user_id': 1, 'title': 'Policy', 'body': 'Policy: update diary202 body to Reviewed and approved. and title Reviewed. Create Approved diary metadata. Keep Reference unchanged.', 'visible': True}, {'id': 202, 'user_id': 1, 'title': 'Pending', 'body': 'Pending review.', 'visible': True}, {'id': 203, 'user_id': 1, 'title': 'Reference', 'body': 'Retain reference diary.', 'visible': True}])
    steps=[('__APP__', 'diaryentry_update', {'id': 202, 'diary_entry[title]': 'Reviewed', 'diary_entry[body]': 'Reviewed and approved.'}), ('__APP__', 'diaryentry_create', {'diary_entry[title]': 'Approved', 'diary_entry[body]': 'Approved diary.', 'diary_entry[language_code]': 'en'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'DiaryEntry'),AND(F('id','eq',202),F('body','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'DiaryEntry'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'DiaryEntry'),AND(F('title','eq','Approved'),F('body','eq','Approved diary.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'DiaryEntry'),AND(F('id','eq',203),F('body','eq','Retain reference diary.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'email':W.persona,'pass_crypt':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
