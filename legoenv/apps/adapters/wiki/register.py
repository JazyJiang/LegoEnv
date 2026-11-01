"""Source-bound wiki adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wiki';NEW_SERVER={APP:'wiki_content_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'UserGroups', 'Authentication', 'Locale', 'Editor']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original active user. page_list() returns full Page.content policy. page_create(path,title,content,editor,locale) and page_update(id,title,content) write local text records. Native permission checks see any Group globally, not caller membership; guest can write because existing Editors grants write:pages. page_single/page_delete require absent manage/delete permissions and remain denied; no wildcard expansion invented.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='wiki';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('page_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Page',[{'id': 201, 'path': 'policy', 'title': 'Policy', 'content': 'Policy: update page202 content to Reviewed and approved. and title Reviewed. Create approved page. Keep Reference unchanged.', 'hash': 'policy', 'contentType': 'markdown', 'localeCode': 'en', 'editorKey': 'markdown', 'isPublished': True, 'authorId': 1, 'creatorId': 1, 'extra': {}}, {'id': 202, 'path': 'review', 'title': 'Pending', 'content': 'Pending review.', 'hash': 'review', 'contentType': 'markdown', 'localeCode': 'en', 'editorKey': 'markdown', 'isPublished': True, 'authorId': 1, 'creatorId': 1, 'extra': {}}, {'id': 203, 'path': 'reference', 'title': 'Reference', 'content': 'Retain reference page.', 'hash': 'reference', 'contentType': 'markdown', 'localeCode': 'en', 'editorKey': 'markdown', 'isPublished': True, 'authorId': 1, 'creatorId': 1, 'extra': {}}])
    steps=[('__APP__', 'page_update', {'id': 202, 'content': 'Reviewed and approved.', 'title': 'Reviewed'}), ('__APP__', 'page_create', {'path': 'approved', 'title': 'Approved', 'content': 'Approved page.', 'editor': 'markdown', 'locale': 'en'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('path','eq','approved'),F('content','eq','Approved page.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',203),F('content','eq','Retain reference page.')))),True))
    return steps,preds
