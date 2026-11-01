"""Pretalx source speaker records, rooms and known-code submission acceptance."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='pretalx';NEW_SERVER={APP:'conference_management'}
CONFIG={'User','GlobalSettings','Organiser','Team','Event','SubmissionType','Track','CfP','UserEventPreferences','AttendeeProfile'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is pretalx. Sign in with {p}__user_login(email,password), as User1; original organiser privileges remain. '
    'speakerprofile_list(event=<numeric event id>,search) reads speakers with optional real substring search; SpeakerProfile.internal_notes carries policy. '
    'speakerprofile_create(event,name,email) creates scalar speaker fields but omits generated code. '
    'speakerprofile_update_orga(event=<id>,code,name,biography,email,internal_notes), speakerprofile_toggle_arrived(event,code), speakerprofile_delete(event,code) operate on known speaker codes. '
    'room_create(event=<slug>,name,guid,description,capacity), room_update(event=<slug>,pk,name,capacity), room_delete(event,pk) operate on known room ids. '
    'room_toggle_hidden(event,pk,hidden=true) only accepts currently unhidden rooms; submission_accept(event=<slug>,code) changes a known submission state. '
    'The source has no Room/Submission read/list interface, and general team/user/event ACLs are incomplete. Original comment-create guard blocks this ordinary-organiser persona. No scheduling constraints, invitation delivery, binary resources or full conference workflow is certified.')}
LOGIN={APP:('user_login','email')}
SERVER.update(NEW_SERVER);PFX[APP]='pretalx';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for event in env.state.get(NS(APP,'Event'),[]):
        result=env.call(NS(APP,'speakerprofile_list'),{'event':event['id']});assert result.get('ok'),result
        rep[APP+' speakerprofile_list '+str(event['id'])]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def speakers(W,rows,src=None):return _append(W,'SpeakerProfile',[{'event':1,'origin':'orga','has_arrived':False,**r} for r in rows],src)
def rooms(W,rows,src=None):return _append(W,'Room',[{'event':1,'hidden':False,**r} for r in rows],src)
def submissions(W,rows,src=None):return _append(W,'Submission',[{'event':1,'submission_type':1,'track':1,'state':'submitted',**r} for r in rows],src)
def smoke_seed(W):
    speakers(W,[{'id':101,'code':'SPK-POLICY','name':'Policy speaker','email':'policy@pretalx.example','internal_notes':'Policy: record the approved organiser note for SPK-REVIEW, mark that speaker arrived and hide room201. Keep SPK-REFERENCE internal notes unchanged.'},
        {'id':102,'code':'SPK-REVIEW','name':'Review speaker','email':'review@pretalx.example','internal_notes':'Review pending.'},
        {'id':103,'code':'SPK-REFERENCE','name':'Reference speaker','email':'reference@pretalx.example','internal_notes':'Retain this reference wording.'}])
    rooms(W,[{'id':201,'name':'Review room','guid':'review-room','capacity':30}])
    submissions(W,[{'id':301,'code':'TALK-REVIEW','title':'Review submission'}])
    steps=[(APP,'speakerprofile_update_orga',{'event':1,'code':'SPK-REVIEW','internal_notes':'Review approved and recorded.'}),(APP,'speakerprofile_toggle_arrived',{'event':1,'code':'SPK-REVIEW'}),(APP,'room_toggle_hidden',{'event':'ops-conference','pk':201,'hidden':True})]
    preds=[('note','Approved organiser note recorded.',CNT(SEL(NS(APP,'SpeakerProfile'),AND(F('id','eq',102),F('internal_notes','eq','Review approved and recorded.')))),False),
        ('arrived','Reviewed speaker marked arrived.',CNT(SEL(NS(APP,'SpeakerProfile'),AND(F('id','eq',102),F('has_arrived','eq',True)))),False),
        ('room','Review room hidden.',CNT(SEL(NS(APP,'Room'),AND(F('id','eq',201),F('hidden','eq',True)))),False),
        ('reference','Reference notes unchanged.',CNT(SEL(NS(APP,'SpeakerProfile'),AND(F('id','eq',103),F('internal_notes','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','speakers','rooms','submissions','smoke_seed']
