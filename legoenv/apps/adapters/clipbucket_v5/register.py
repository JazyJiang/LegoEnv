"""Source-bound clipbucket_v5 adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='clipbucket_v5';NEW_SERVER={APP:'video_collection_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserLevel', 'Sort']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). video_search(q=Policy) reads genuine Video.description policy. collection_create(collection_name,collection_description,type), collection_update(collection_id,collection_name,collection_description,type,public_upload,allow_comments,allow_rating), collection_delete(cid) edit own Collection metadata with original owner/admin guard. There is no source Collection read endpoint; no video transcoding, playback, binary upload or delivery effect certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='clipbucket_v5';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('video_search', {'q':'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;assert r.get('result') and any('Policy:' in row.get('description','') for row in r['result']),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Collection',[{'id':101,'collection_id':101,'collection_name':'Operations','collection_description':'Operations collection.','userid':1,'type':'videos','broadcast':'public','active':'yes','public_upload':'no'},{'id':102,'collection_id':102,'collection_name':'Pending','collection_description':'Pending review.','userid':1,'type':'videos','broadcast':'public','active':'yes','public_upload':'no'},{'id':103,'collection_id':103,'collection_name':'Reference','collection_description':'Reference collection.','userid':1,'type':'videos','broadcast':'public','active':'yes','public_upload':'no'}])
    records(W,'Video',[{'id': 201, 'videoid': 201, 'videokey': 'policy-video', 'userid': 1, 'title': 'Policy', 'description': 'Policy: set collection102 description Reviewed and approved. and name Reviewed. Create Approved videos collection. Keep Reference unchanged.', 'file_name': 'policy.mp4', 'broadcast': 'public', 'active': 'yes', 'status': 'Successful'}, {'id': 202, 'videoid': 202, 'videokey': 'review-video', 'userid': 1, 'title': 'Review', 'description': 'Review context.', 'file_name': 'review.mp4', 'broadcast': 'public', 'active': 'yes', 'status': 'Successful'}, {'id': 203, 'videoid': 203, 'videokey': 'reference-video', 'userid': 1, 'title': 'Reference', 'description': 'Retain reference video.', 'file_name': 'reference.mp4', 'broadcast': 'public', 'active': 'yes', 'status': 'Successful'}])
    steps=[('__APP__', 'collection_update', {'collection_id': 102, 'collection_description': 'Reviewed and approved.', 'type': 'videos', 'public_upload': 'no', 'allow_comments': 'yes', 'allow_rating': 'yes'}), ('__APP__', 'collection_update', {'collection_id': 102, 'collection_name': 'Reviewed', 'type': 'videos', 'public_upload': 'no', 'allow_comments': 'yes', 'allow_rating': 'yes'}), ('__APP__', 'collection_create', {'collection_name': 'Approved', 'collection_description': 'Approved collection.', 'type': 'videos', 'public_upload': 'no', 'allow_comments': 'yes', 'allow_rating': 'yes'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_id','eq',102),F('collection_description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_id','eq',102),F('collection_name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_name','eq','Approved'),F('userid','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Video'),AND(F('videoid','eq',203),F('description','eq','Retain reference video.')))),True))
    return steps,preds
