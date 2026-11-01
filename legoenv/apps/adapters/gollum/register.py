'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound gollum adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='gollum';NEW_SERVER={APP:'gollum_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['']]}
NEW_NOTES={APP:'{p}__ has no source authentication or account entity; complete admission blocked. Public page_read(path) returns Page.content policy. page_create(page,format,content), page_edit(path,content,format), page_delete(path) modify wiki rows. No real git commit/etag processing/rendering/file bytes or authorization added.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='gollum';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('page_read', {'path': 'Policy.md'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Page',[{'id': 201, 'path': 'Policy.md', 'content': 'Policy: update Review.md content to Reviewed and approved. and format to markdown. Create Approved.md. Keep Reference unchanged.', 'format': 'markdown'}, {'id': 202, 'path': 'Review.md', 'content': 'Pending review.', 'format': 'text'}, {'id': 203, 'path': 'Reference.md', 'content': 'Retain reference page.', 'format': 'markdown'}])
    steps=[('__APP__', 'page_edit', {'path': 'Review.md', 'content': 'Reviewed and approved.'}), ('__APP__', 'page_edit', {'path': 'Review.md', 'format': 'markdown'}), ('__APP__', 'page_create', {'page': 'Approved.md', 'format': 'markdown', 'content': 'Approved page.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('path','eq','Review.md'),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('path','eq','Review.md'),F('format','eq','markdown')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('path','eq','Approved.md'),F('content','eq','Approved page.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('path','eq','Reference.md'),F('content','eq','Retain reference page.')))),True))
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
