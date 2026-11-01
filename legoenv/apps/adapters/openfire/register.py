"""Openfire original room and group metadata; no invented messaging tool."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='openfire';NEW_SERVER={APP:'xmpp_administration'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','MucService')]}
NEW_NOTES={APP:('{p}__ is Openfire metadata administration. Sign in with {p}__sign_in(username,password), as User1; text usernames remain business identities. '
    'mucroom_search(serviceID,query) lists rooms within a MucService; MucRoom.description carries policy. '
    'mucroom_changesubject(roomID,subject) requires canChangeSubject=true. mucroom_create(serviceID,roomName,naturalName,description) creates scalar room metadata, not a full channel. '
    'group_create(groupName,description), group_update(groupName,description), group_delete(groupName) operate on named groups. '
    'group_addmember(groupName,username,administrator), group_setmemberadministrator(groupName,username,administrator), group_removemember(groupName,username) operate on membership rows. '
    'No Group read/list or chat/DM send interface exists; group names must be known. rosteritem_getroster(jid) reads your roster with optional JID substring. '
    'Network messaging, privacy/lockout enforcement, full room provisioning and comprehensive admin/room/node ACLs are not certified.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='openfire';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('rosteritem_getroster',{})]+[('mucroom_search',{'serviceID':r['serviceID']}) for r in env.state.get(NS(APP,'MucService'),[])]+[('mucroom_listaffiliations',{'roomID':r['roomID']}) for r in env.state.get(NS(APP,'MucRoom'),[])]
    for tool,args in reads:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def rooms(W,rows,src=None):return _append(W,'MucRoom',[{'id':r['roomID'],'serviceID':1,'canChangeSubject':True,'publicRoom':True,'subject':'Review pending.',**r} for r in rows],src)
def groups(W,rows,src=None):return _append(W,'Group',rows,src)
def smoke_seed(W):
    rooms(W,[{'roomID':101,'name':'policy','naturalName':'Policy room','description':'Policy: change room102 subject to Reviewed and approved., update review-group description, and add the colleague as a non-admin member. Keep room103 description unchanged.'},
        {'roomID':102,'name':'review','naturalName':'Review room','description':'Review context.'},{'roomID':103,'name':'reference','naturalName':'Reference room','description':'Retain this reference wording.'}])
    groups(W,[{'id':201,'groupName':'review-group','description':'Review pending.'}])
    _append(W,'MucAffiliation',[{'id':301,'roomID':101,'jid':W.persona,'affiliation':10}])
    steps=[(APP,'mucroom_changesubject',{'roomID':102,'subject':'Reviewed and approved.'}),(APP,'group_update',{'groupName':'review-group','description':'Review approved and recorded.'}),(APP,'group_addmember',{'groupName':'review-group','username':'colleague@openfire.example','administrator':False})]
    preds=[('subject','Reviewed room subject recorded.',CNT(SEL(NS(APP,'MucRoom'),AND(F('roomID','eq',102),F('subject','eq','Reviewed and approved.')))),False),
        ('group','Approved group description recorded.',CNT(SEL(NS(APP,'Group'),AND(F('groupName','eq','review-group'),F('description','eq','Review approved and recorded.')))),False),
        ('member','Colleague added as non-admin member.',CNT(SEL(NS(APP,'GroupUser'),AND(F('groupName','eq','review-group'),F('username','eq','colleague@openfire.example'),F('administrator','eq',False)))),False),
        ('reference','Reference room description unchanged.',CNT(SEL(NS(APP,'MucRoom'),AND(F('roomID','eq',103),F('description','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','rooms','groups','smoke_seed']
