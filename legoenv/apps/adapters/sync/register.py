"""Source-bound sync adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='sync';NEW_SERVER={APP:'sync_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_login(name,password). user_acpsearchusers(field=name,value=persona) returns existing User.profile object whose text is the source-defined short profile blurb. That actual narrative text carries policy. playlist_save(name,contents,count,duration) upserts own saved-playlist metadata; playlist_delete(name) deletes own. Native list owner binding uses text session.name. No channel streaming/network effects.'}
LOGIN={APP:('user_login','name')};SERVER.update(NEW_SERVER);PFX[APP]='sync';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('user_acpsearchusers', {'field': 'name', 'value': 'ops@sync.example'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok') and 'Policy:' in json.dumps(r),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'UserPlaylist',[{'id': 201, 'user': 'ops@sync.example', 'name': 'policy-metadata', 'contents': [], 'count': 0, 'duration': 0}, {'id': 202, 'user': 'ops@sync.example', 'name': 'review', 'contents': [], 'count': 0, 'duration': 0}, {'id': 203, 'user': 'ops@sync.example', 'name': 'reference', 'contents': [], 'count': 0, 'duration': 0}])
    steps=[('__APP__', 'playlist_save', {'name': 'review', 'contents': [], 'count': 2, 'duration': 120}), ('__APP__', 'playlist_save', {'name': 'approved', 'contents': [], 'count': 1, 'duration': 60})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'UserPlaylist'),AND(F('name','eq','review'),F('count','eq',2)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'UserPlaylist'),AND(F('name','eq','review'),F('duration','eq',120)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'UserPlaylist'),AND(F('name','eq','approved'),F('count','eq',1),F('duration','eq',60)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'UserPlaylist'),AND(F('name','eq','reference'),F('duration','eq',0)))),True))
    return steps,preds
