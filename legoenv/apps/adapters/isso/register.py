'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound isso adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='isso';NEW_SERVER={APP:'isso_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Thread']]}
NEW_NOTES={APP:'{p}__ has no source login/account/password interface, so full admission blocked. comment_view(id) returns genuine Comment.text policy. comment_new(uri,text,author), comment_edit(id,text,author), comment_delete(id) operate public rows. Native new comment mode is2; source view/edit/delete only check existence and do not require ownership proof. No real cookie signing/markdown/email.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='isso';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('comment_view', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id': 201, 'tid': 1, 'text': 'Policy: update comment202 text to Reviewed and approved. and author Reviewed. Add Approved comment on /posts/introducing-isso. Keep Reference unchanged.', 'author': 'Policy', 'mode': 1, 'voters': []}, {'id': 202, 'tid': 1, 'text': 'Pending review.', 'author': 'Pending', 'mode': 1, 'voters': []}, {'id': 203, 'tid': 1, 'text': 'Retain reference comment.', 'author': 'Reference', 'mode': 1, 'voters': []}])
    steps=[('__APP__', 'comment_edit', {'id': 202, 'text': 'Reviewed and approved.', 'author': 'Reviewed'}), ('__APP__', 'comment_new', {'uri': '/posts/introducing-isso', 'text': 'Approved comment.', 'author': 'Approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('text','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('author','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('text','eq','Approved comment.'),F('tid','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',203),F('text','eq','Retain reference comment.')))),True))
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
