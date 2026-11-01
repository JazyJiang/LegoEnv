'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound owncast adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='owncast';NEW_SERVER={APP:'owncast_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserAccessToken', 'Auth', 'Datastore']]}
NEW_NOTES={APP:'{p}__ has no source password-verifying login/account interface; full admission blocked. message_readpublichistory(accessToken=tok-viewer) reads Message.body policy using genuine source viewer token. Config setters update welcome/title/chat Datastore values only and merely check admin_password_key exists. No viewer token or admin secret verification, actual streaming, network or federation effects invented.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='owncast';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('message_readpublichistory', {'accessToken': 'tok-viewer'}), ('config_getwebconfig', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Message',[{'id': 201, 'user_id': 'u_admin', 'body': 'Policy: set welcome message to Reviewed and approved., stream title Reviewed and chat_disabled true. Keep Reference unchanged.', 'eventType': 'CHAT', 'hidden_at': None}, {'id': 202, 'user_id': 'u_admin', 'body': 'Review context.', 'eventType': 'CHAT', 'hidden_at': None}, {'id': 203, 'user_id': 'u_admin', 'body': 'Retain reference message.', 'eventType': 'CHAT', 'hidden_at': None}])
    steps=[('__APP__', 'config_setserverwelcomemessage', {'value': 'Reviewed and approved.'}), ('__APP__', 'config_setstreamtitle', {'value': 'Reviewed'}), ('__APP__', 'config_setchatdisabled', {'value': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Datastore'),AND(F('key','eq','server_welcome_message'),F('value','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Datastore'),AND(F('key','eq','stream_title'),F('value','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Datastore'),AND(F('key','eq','chat_disabled'),F('value','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Message'),AND(F('id','eq',203),F('body','eq','Retain reference message.')))),True))
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None
