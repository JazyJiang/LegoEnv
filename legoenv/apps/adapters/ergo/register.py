"""Source-bound ergo adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ergo';NEW_SERVER={APP:'ergo_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Account']]}
NEW_NOTES={APP:'{p}__ sign_in(name_casefolded,credentials) uses source named password argument credentials. channel_getsettings(channel,setting) returns full channel including topic policy; channel_listchannels() lists records. channel_register(channel), channel_settopic(channel,topic), channel_unregister(channel,code) update local channel metadata. Founder remains original text account name via explicit session binding. Source topic edit only checks channel existence; unregister checks founder but not code value. No IRC sockets/messages/history delivery.'}
LOGIN={APP:('sign_in','name_casefolded')};SERVER.update(NEW_SERVER);PFX[APP]='ergo';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'name_casefolded':self.persona,'credentials':self.password}).get('ok')
    for t,args in [('channel_getsettings', {'channel': '#policy', 'setting': 'topic'}), ('channel_listchannels', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'RegisteredChannel',[{'id': 201, 'uuid': 201, 'name': '#policy', 'founder': 'ada', 'topic': 'Policy: set #review topic to Reviewed and approved. Register #approved. Set #approved topic to Approved channel. Keep Reference unchanged.'}, {'id': 202, 'uuid': 202, 'name': '#review', 'founder': 'ada', 'topic': 'Pending review.'}, {'id': 203, 'uuid': 203, 'name': '#reference', 'founder': 'ada', 'topic': 'Retain reference topic.'}])
    steps=[('__APP__', 'channel_settopic', {'channel': '#review', 'topic': 'Reviewed and approved.'}), ('__APP__', 'channel_register', {'channel': '#approved'}), ('__APP__', 'channel_settopic', {'channel': '#approved', 'topic': 'Approved channel.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'RegisteredChannel'),AND(F('name','eq','#review'),F('topic','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'RegisteredChannel'),AND(F('name','eq','#approved'),F('founder','eq','ada')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'RegisteredChannel'),AND(F('name','eq','#approved'),F('topic','eq','Approved channel.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'RegisteredChannel'),AND(F('name','eq','#reference'),F('topic','eq','Retain reference topic.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'name_casefolded':W.persona,'credentials':W.password})]+[(lambda e,t=t,args=args:e.call(NS(APP,t),args)) for _,t,args in steps]
    return steps,preds
