"""Original Radicale calendar-item and collection scalar interfaces."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='radicale';NEW_SERVER={APP:'calendar_storage'};NEW_CONTENT={APP:['Collection','CalendarItem','Share','SyncToken']}
NEW_NOTES={APP:('{p}__ is calendar storage metadata. sign_in(login,password) verifies Account1. calendaritem_search(path,component) and calendaritem_get(collection_path,href) read serialized iCalendar/vCard; CalendarItem.serialized carries policy. calendaritem_upload(collection_path,href,serialized) inserts or overwrites raw text. collection_create(path,tag), collection_create_calendar(path,parent_path,displayname), collection_set_meta(path,...), collection_delete(path), calendaritem_move(href,from_collection,to_collection), calendaritem_delete(collection_path,href) are scalar writes. share_create_map(PathMapped,User,PathOrToken), share_update, share_toggle, share_delete operate metadata; share_list is owner scoped. No collection read/list, serialized-content parsing, DAV/network effects or general ownership ACL is certified.')}
LOGIN={APP:('sign_in','login')};SERVER.update(NEW_SERVER);PFX[APP]='radicale';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'login':self.persona,'password':self.password}).get('ok')
    reads=[('share_list',{})]+[(t,{'path':r['path']}) for t in ['calendaritem_search','calendaritem_propfind'] for r in env.state.get(NS(APP,'Collection'),[])]
    for tool,args in reads:
        r=env.call(NS(APP,tool),args);assert r.get('ok'),r;rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def collections(W,rows,src=None):return _append(W,'Collection',[{'owner':W.persona,**r} for r in rows],src)
def items(W,rows,src=None):return _append(W,'CalendarItem',rows,src)
def smoke_seed(W):
    collections(W,[{'id':101,'path':'/ops/','tag':'VCALENDAR','displayname':'Operations'}])
    items(W,[{'id':201,'href':'policy.ics','collection_path':'/ops/','component_name':'VEVENT','serialized':'BEGIN:VCALENDAR\nX-POLICY:Update review.ics to approved text; update collection title to Reviewed operations; create approved.ics. Keep reference.ics unchanged.\nEND:VCALENDAR'},{'id':202,'href':'review.ics','collection_path':'/ops/','component_name':'VEVENT','serialized':'BEGIN:VCALENDAR\nSUMMARY:Pending\nEND:VCALENDAR'},{'id':203,'href':'reference.ics','collection_path':'/ops/','component_name':'VEVENT','serialized':'Reference calendar text retained.'}])
    steps=[(APP,'calendaritem_upload',{'collection_path':'/ops/','href':'review.ics','serialized':'BEGIN:VCALENDAR\nSUMMARY:Approved\nEND:VCALENDAR'}),(APP,'collection_set_meta',{'path':'/ops/','displayname':'Reviewed operations'}),(APP,'calendaritem_upload',{'collection_path':'/ops/','href':'approved.ics','serialized':'BEGIN:VCALENDAR\nSUMMARY:Approved record\nEND:VCALENDAR'})]
    preds=[('review','Approved raw calendar text persisted.',CNT(SEL(NS(APP,'CalendarItem'),AND(F('href','eq','review.ics'),F('serialized','contains','SUMMARY:Approved')))),False),('title','Collection title updated.',CNT(SEL(NS(APP,'Collection'),AND(F('path','eq','/ops/'),F('displayname','eq','Reviewed operations')))),False),('created','Calendar item created.',CNT(SEL(NS(APP,'CalendarItem'),F('href','eq','approved.ics'))),False),('reference','Reference text unchanged.',CNT(SEL(NS(APP,'CalendarItem'),AND(F('href','eq','reference.ics'),F('serialized','eq','Reference calendar text retained.')))),True)]
    return steps,preds
