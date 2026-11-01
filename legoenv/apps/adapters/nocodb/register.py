"""Source-bound nocodb adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='nocodb';NEW_SERVER={APP:'nocodb_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Model', 'Source', 'Base', 'BaseUser', 'Workspace', 'WorkspaceUser', 'Org', 'OrgUser']]}
NEW_NOTES={APP:'{p}__ signin(email,password) uses original User. list_comments(fk_model_id,row_id) reads Comment.comment policy but source ignores supplied model/row filters. comment_row(fk_model_id,comment) appends local comment, update_comment(commentId,comment) edits, delete_comment(commentId) sets is_deleted. Source author guard checks any own comment, not target; any member with one own row can edit/delete another. No dynamic table/automation/AI execution.'}
LOGIN={APP:('signin','email')};SERVER.update(NEW_SERVER);PFX[APP]='nocodb';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'signin'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('list_comments', {'fk_model_id': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id': 201, 'fk_model_id': 1, 'row_id': 'policy', 'comment': 'Policy: update comment202 to Reviewed and approved. Add Approved comment. and Review complete. comments to model1. Keep Reference unchanged.', 'created_by': 1, 'is_deleted': False}, {'id': 202, 'fk_model_id': 1, 'row_id': 'review', 'comment': 'Pending review.', 'created_by': 1, 'is_deleted': False}, {'id': 203, 'fk_model_id': 1, 'row_id': 'reference', 'comment': 'Retain reference comment.', 'created_by': 1, 'is_deleted': False}])
    steps=[('__APP__', 'update_comment', {'commentId': 202, 'comment': 'Reviewed and approved.'}), ('__APP__', 'comment_row', {'fk_model_id': 1, 'comment': 'Approved comment.'}), ('__APP__', 'comment_row', {'fk_model_id': 1, 'comment': 'Review complete.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('comment','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment','eq','Approved comment.'),F('created_by','eq',1)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment','eq','Review complete.'),F('created_by','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',203),F('comment','eq','Retain reference comment.')))),True))
    return steps,preds
