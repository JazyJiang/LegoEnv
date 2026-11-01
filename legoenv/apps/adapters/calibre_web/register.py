'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound calibre_web adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='calibre_web';NEW_SERVER={APP:'calibre_web_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Books', 'Authors', 'Tags', 'Series', 'Comments', 'Data']]}
NEW_NOTES={APP:'{p}__ user_login(name,password) uses original User. web_showbook(book_id) returns Books metadata without Comments.text join or book bytes, so readable narrative carrier admission blocked. Independent shelf_create(title), shelf_edit(shelf_id,title,is_public,kobo_sync), shelf_delete(shelf_id) mutate own Shelf metadata. No eBook content, conversion, email/reader delivery or Kobo synchronization executed.'}
LOGIN={APP:('user_login','name')};SERVER.update(NEW_SERVER);PFX[APP]='calibre_web';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('web_showbook', {'book_id': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source-readable business policy text carrier; do not fabricate a read tool or repurpose metadata as instructions. Complete admission blocked.')
def metadata_smoke_seed(W):
    records(W,'Shelf',[{'id': 201, 'uuid': 'operations', 'name': 'Operations', 'user_id': 1, 'is_public': 0, 'kobo_sync': False}, {'id': 202, 'uuid': 'review', 'name': 'Pending', 'user_id': 1, 'is_public': 0, 'kobo_sync': False}, {'id': 203, 'uuid': 'reference', 'name': 'Reference', 'user_id': 1, 'is_public': 0, 'kobo_sync': False}])
    steps=[('__APP__', 'shelf_edit', {'shelf_id': 202, 'title': 'Reviewed', 'is_public': True}), ('__APP__', 'shelf_create', {'title': 'Approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Shelf'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Shelf'),AND(F('id','eq',202),F('is_public','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Shelf'),AND(F('name','eq','Approved'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Shelf'),AND(F('id','eq',203),F('name','eq','Reference')))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
