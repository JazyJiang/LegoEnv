"""Source-bound hedgedoc adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='hedgedoc';NEW_SERVER={APP:'hedgedoc_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Identity', 'Group', 'GroupUser']]}
NEW_NOTES={APP:'{p}__ sign_in(provider_user_id,password_hash). get_note_content(noteId=201) reads real Revision.content. change_note_visibility(noteId,publiclyVisible) edits native visibility; add_note_alias(noteId,newAlias) inserts alias; remove_note_alias(noteId,alias) removes nonprimary null marker alias. Source read/visibility/alias guards lack owner check; actual cross-owner effects documented.'}
LOGIN={APP:('sign_in','provider_user_id')};SERVER.update(NEW_SERVER);PFX[APP]='hedgedoc';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'provider_user_id':self.persona,'password_hash':self.password}).get('ok')
    for t,args in [('get_note_content', {'noteId': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Note',[{'id':i,'owner_id':1,'publicly_visible':True,'version':1} for i in (201,202,203)])
    records(W,'Revision',[{'id': 201, 'uuid': 'revision-policy', 'note_id': 201, 'content': 'Policy: make note202 private and attach approved-a and approved-b aliases. Keep Reference unchanged.'}, {'id': 202, 'uuid': 'revision-review', 'note_id': 202, 'content': 'Pending review.'}, {'id': 203, 'uuid': 'revision-reference', 'note_id': 203, 'content': 'Retain reference note.'}])
    steps=[('__APP__', 'change_note_visibility', {'noteId': 202, 'publiclyVisible': False}), ('__APP__', 'add_note_alias', {'noteId': 202, 'newAlias': 'approved-a'}), ('__APP__', 'add_note_alias', {'noteId': 202, 'newAlias': 'approved-b'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Note'),AND(F('id','eq',202),F('publicly_visible','eq',False)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('note_id','eq',202),F('alias','eq','approved-a')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('note_id','eq',202),F('alias','eq','approved-b')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Revision'),AND(F('uuid','eq','revision-reference'),F('content','eq','Retain reference note.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'provider_user_id':W.persona,'password_hash':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
