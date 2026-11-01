'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound cryptpad adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='cryptpad';NEW_SERVER={APP:'cryptpad_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['LoginBlock']]}
NEW_NOTES={APP:'{p}__ Complete admission blocked: original LoginBlock has no seed email credential and content is encrypted block data; no persona login or readable plaintext policy invented. Native channelmetadata_get(channel) reads metadata. channel_trimhistory(channel,hash) publicly sets local messages=null after metadata-existence check; hash is only required text, not validated proof. No pad plaintext or collaboration certified.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='cryptpad';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('channelmetadata_get', {'channel': 201})]:
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
    for row,content in zip(W.spec[APP]['seed_state']['LoginBlock'],['{\"name\":\"Ada\",\"version\":\"4.0\"}','{\"name\":\"Grace\",\"version\":\"4.0\"}']):row['content']=content
    records(W,'ChannelMetadata',[{'id':i,'channelId':i,'restricted':True,'owners':[]} for i in (201,202,203,204)])
    records(W,'Channel',[{'id': 201, 'channelId': 201, 'messages': ['ciphertext-fixture-1']}, {'id': 202, 'channelId': 202, 'messages': ['ciphertext-fixture-2']}, {'id': 203, 'channelId': 203, 'messages': ['ciphertext-fixture-3']}, {'id': 204, 'channelId': 204, 'messages': []}])
    steps=[('__APP__', 'channel_trimhistory', {'channel': 201, 'hash': 'required-only-fixture'}), ('__APP__', 'channel_trimhistory', {'channel': 202, 'hash': 'required-only-fixture'}), ('__APP__', 'channel_trimhistory', {'channel': 203, 'hash': 'required-only-fixture'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Channel'),AND(F('channelId','eq',201),F('messages','is_null')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Channel'),AND(F('channelId','eq',202),F('messages','is_null')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Channel'),AND(F('channelId','eq',203),F('messages','is_null')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Channel'),AND(F('channelId','eq',204),F('messages','eq',{'const': []})))),True))
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
