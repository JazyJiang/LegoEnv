"""Source-bound gokapi adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='gokapi';NEW_SERVER={APP:'upload_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password). filerequest_list reads own UploadRequest.note policy; file_list reads own file metadata. filerequest_create(name,notes), filerequest_delete(id), file_upload(filename,allowedDownloads,expiryDays), file_edit(id,allowedDownloads,expiryTimestamp) write scalar metadata. file_delete(id) only sets ExpireAt=0/UnlimitedTime=false; file_restore(id) only clears PendingDeletion. No file bytes, actual expiry scheduler/download, password hashing or encryption certified. Existing filerequest_edit does not replace name/notes.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='gokapi';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('filerequest_list', {}), ('file_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'UploadRequest',[{'id':101,'userid':1,'name':'Policy request','note':'Policy: create Reviewed operations request, set file201 allowedDownloads to3 and expiry to2026-10-30. Keep reference request103 note unchanged.'},{'id':102,'userid':1,'name':'Review request','note':'Review context.'},{'id':103,'userid':1,'name':'Reference request','note':'Retain reference request note.'}]);records(W,'File',[{'id':201,'Id':201,'UserId':1,'Name':'review.txt','DownloadsRemaining':5,'ExpireAt':'2030-01-01T00:00:00','PendingDeletion':0}])
    steps=[(APP,'filerequest_create',{'name':'Reviewed operations','notes':'Reviewed request note.'}),(APP,'file_edit',{'id':201,'allowedDownloads':3}),(APP,'file_edit',{'id':201,'expiryTimestamp':'2026-10-30T09:00:00'})]
    preds=[('request','Owned upload request created.',CNT(SEL(NS(APP,'UploadRequest'),AND(F('name','eq','Reviewed operations'),F('note','eq','Reviewed request note.')))),False),('count','Download limit metadata updated.',CNT(SEL(NS(APP,'File'),AND(F('Id','eq',201),F('DownloadsRemaining','eq',3)))),False),('expiry','Expiry metadata updated.',CNT(SEL(NS(APP,'File'),AND(F('Id','eq',201),F('ExpireAt','eq','2026-10-30T09:00:00')))),False),('reference','Reference note unchanged.',CNT(SEL(NS(APP,'UploadRequest'),AND(F('id','eq',103),F('note','eq','Retain reference request note.')))),True)]
    return steps,preds
