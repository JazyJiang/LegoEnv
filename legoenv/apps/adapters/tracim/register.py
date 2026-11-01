"""Source-bound tracim adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='tracim';NEW_SERVER={APP:'workspace_revision_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Workspace', 'UserWorkspaceConfig']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(email,password); User1 retains original ADMIN profile. contentapi_get_workspace_content(workspace_id,label) reads revision rows; ContentRevisionRO.raw_content carries policy. contentapi_search_content(search_string) is literal substring without full workspace security. contentapi_update_content(content_id,workspace_id,raw_content,label) APPENDS an edition revision; it does not edit old revisions or update Content.cached_revision_id. contentapi_create_comment(workspace_id,content_id,raw_content) appends comment revision metadata. workspaceapi_update_workspace(workspace_id,description) edits scalar metadata; taglib_add(workspace_id,tag_name), taglib_delete(workspace_id,tag_id) modify tags. No current-revision resolution, complete publication/status/move/archive, binary file processing or notification delivery certified.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='tracim';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('contentapi_get_workspace_content', {'workspace_id': 1}), ('contentapi_search_content', {'search_string': 'Retain'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Content',[{'id':201,'cached_revision_id':301},{'id':202,'cached_revision_id':302},{'id':203,'cached_revision_id':303}]);records(W,'ContentRevisionRO',[{'id':301,'revision_id':301,'content_id':201,'workspace_id':1,'owner_id':1,'type':'html-document','label':'Policy','raw_content':'Policy: append an edition revision for content202 containing Reviewed and approved.; update workspace1 description to Reviewed workspace.; create Reviewed operations tag. Keep reference revision303 raw_content unchanged.','status':'open'},{'id':302,'revision_id':302,'content_id':202,'workspace_id':1,'owner_id':1,'type':'html-document','label':'Review','raw_content':'Original review body.','status':'open'},{'id':303,'revision_id':303,'content_id':203,'workspace_id':1,'owner_id':1,'type':'html-document','label':'Reference','raw_content':'Retain reference revision body.','status':'open'}])
    steps=[(APP,'contentapi_update_content',{'workspace_id':1,'content_id':202,'label':'Reviewed edition','raw_content':'Reviewed and approved.'}),(APP,'workspaceapi_update_workspace',{'workspace_id':1,'description':'Reviewed workspace.'}),(APP,'taglib_add',{'workspace_id':1,'tag_name':'Reviewed operations'})]
    preds=[('revision','New edition revision appended.',CNT(SEL(NS(APP,'ContentRevisionRO'),AND(F('content_id','eq',202),F('raw_content','eq','Reviewed and approved.'),F('revision_type','eq','edition')))),False),('workspace','Workspace scalar description updated.',CNT(SEL(NS(APP,'Workspace'),AND(F('workspace_id','eq',1),F('description','eq','Reviewed workspace.')))),False),('tag','Workspace tag created.',CNT(SEL(NS(APP,'Tag'),AND(F('workspace_id','eq',1),F('tag_name','eq','Reviewed operations')))),False),('reference','Reference revision unchanged.',CNT(SEL(NS(APP,'ContentRevisionRO'),AND(F('revision_id','eq',303),F('raw_content','eq','Retain reference revision body.')))),True)]
    return steps,preds
