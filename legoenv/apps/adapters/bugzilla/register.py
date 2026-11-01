"""Source-bound bugzilla adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='bugzilla';NEW_SERVER={APP:'bug_review_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Profile', 'Product', 'Component', 'Version', 'Milestone', 'Group', 'UserGroupMap', 'BugStatus', 'StatusWorkflow']]}
NEW_NOTES={APP:'{p}__ sign_in(login_name,cryptpassword) uses original Profile. comment_read(ids) reads Comment.thetext policy but source ignores ids/private filtering. bug_get(ids) lists visible metadata, also ignores ids. bug_update(id,priority,status,resolution) sets source scalar fields; summary/assignee aliases and workflow authorization are not implemented. bug_add_comment(id,comment) appends genuine text. No bug delete tool or email delivery invented.'}
LOGIN={APP:('sign_in','login_name')};SERVER.update(NEW_SERVER);PFX[APP]='bugzilla';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'login_name':self.persona,'cryptpassword':self.password}).get('ok')
    for t,args in [('comment_read', {'ids': [101, 102, 103]}), ('bug_get', {'ids': [101, 102, 103]})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Bug',[{'id':101,'bug_id':101,'product_id':1,'component_id':1,'short_desc':'Policy bug','bug_status':'NEW','priority':'P3','assigned_to':2,'reporter':1,'version':'unspecified'},{'id':102,'bug_id':102,'product_id':1,'component_id':1,'short_desc':'Review bug','bug_status':'NEW','priority':'P3','assigned_to':2,'reporter':1,'version':'unspecified'},{'id':103,'bug_id':103,'product_id':1,'component_id':1,'short_desc':'Reference bug','bug_status':'NEW','priority':'P3','assigned_to':2,'reporter':1,'version':'unspecified'}])
    records(W,'Comment',[{'id': 201, 'comment_id': 201, 'bug_id': 101, 'who': 1, 'thetext': 'Policy: set bug102 priority P1 and status RESOLVED with resolution FIXED. Append Reviewed and approved. comment to bug102. Keep Reference unchanged.', 'isprivate': False}, {'id': 202, 'comment_id': 202, 'bug_id': 102, 'who': 1, 'thetext': 'Pending review.', 'isprivate': False}, {'id': 203, 'comment_id': 203, 'bug_id': 103, 'who': 1, 'thetext': 'Retain reference comment.', 'isprivate': False}])
    steps=[('__APP__', 'bug_update', {'id': 102, 'priority': 'P1'}), ('__APP__', 'bug_update', {'id': 102, 'status': 'RESOLVED', 'resolution': 'FIXED'}), ('__APP__', 'bug_add_comment', {'id': 102, 'comment': 'Reviewed and approved.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Bug'),AND(F('bug_id','eq',102),F('priority','eq','P1')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Bug'),AND(F('bug_id','eq',102),F('bug_status','eq','RESOLVED'),F('resolution','eq','FIXED')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('bug_id','eq',102),F('thetext','eq','Reviewed and approved.'),F('who','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment_id','eq',203),F('thetext','eq','Retain reference comment.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'login_name':W.persona,'cryptpassword':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
