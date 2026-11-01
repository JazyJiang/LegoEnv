"""HumHub scalar posts, comments and content-state operations."""
import json
import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP='humhub'
NEW_SERVER={APP:'social_intranet'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','ContentContainer')]}
NEW_NOTES={APP:(
    '{p}__ is the HumHub intranet. Sign in with {p}__sign_in(email,password); you are User 1. '
    'search_content(keyword,contentType,author,contentContainer) lists only published Content metadata; '
    'keyword is an optional substring of object_model/object_id, author is User.guid and contentContainer '
    'is ContentContainer.guid. Use known GUIDs because unresolved optional references act as omitted filters. '
    'Use get_post(id=object_id) to read a post message. Post.id and Content.id '
    'are different identities: get_post/edit_post use Post.id; publish_draft/pin/archive/delete_content '
    'and visibility actions use Content.id. Policy posts are carried in Post.message. '
    'create_post(message) creates only a scalar Post row: it does not create or publish a matching '
    'Content row, so it is not a full channel-publication interface. edit_post(id,message) updates text. '
    'create_comment(objectModel="post/Post",objectId=<Post id>,message) requires an existing published '
    'Content wrapper. list_comments(objectModel,objectId,q) reads its comments; edit_comment(id,message) '
    'and delete_comment(id) require the author. publish_draft(id=<Content id>) changes draft state 10 '
    'to published state 1. pin_content/unpin_content and set_content_visibility update scalar flags; '
    'archive_content sets archived=true, while delete_content soft-deletes to state 100. '
    'upload_file(files,file_name,mime_type,size,guid) records File metadata only; binary transfer and '
    'object attachment are not represented. delete_file(guid) requires its uploader; download_file '
    'returns metadata, subject to the source guard. move_content deletes its Content row rather than '
    'moving it; schedule_content writes a date without implementing scheduled-state transition. '
    'Comment locks and general content access permissions are not fully enforced; mark_notifications_seen '
    'updates only one matching row. There is no direct-message, space creation or membership write tool.'
)}
LOGIN={APP:('sign_in','email')}
SERVER.update(NEW_SERVER);PFX[APP]='humhub';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
packlib.LOGIN.update(LOGIN)

OBS_READS=['search_content','list_comments','list_friends','count_likes','search_move_targets','get_post']
_original_obs=World.obs_report

def _obs_report(self):
    rep,bad=_original_obs(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    login=env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password})
    if not login.get('ok'):raise RuntimeError(f'HumHub observation login failed: {login}')
    reads=[('search_content',{}),('list_friends',{})]
    for post in env.state.get(NS(APP,'Post'),[]):
        reads += [('get_post',{'id':post['id']}),
                  ('list_comments',{'objectModel':'post/Post','objectId':post['id']}),
                  ('count_likes',{'contentModel':'post/Post','contentId':post['id']})]
    for content in env.state.get(NS(APP,'Content'),[]):
        reads.append(('search_move_targets',{'contentId':content['id']}))
    for tool,args in reads:
        result=env.call(NS(APP,tool),args)
        if not result.get('ok'):raise RuntimeError(f'HumHub observation {tool} failed: {result}')
        key=f'{APP} {tool}'+(' '+json.dumps(args,sort_keys=True) if args else '')
        rep[key]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{key:size for key,size in rep.items() if size>OBS_CAP}

World.obs_report=_obs_report

def _append(W,entity,rows,src=None):
    rows=[dict(row) for row in rows]
    for row in rows:
        if 'id' in row and (not isinstance(row['id'],int) or isinstance(row['id'],bool)):
            raise ValueError(f'{entity} seed ids must be integers')
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows

def spaces(W,rows,src=None):
    for row in rows:
        cid=row.get('contentcontainer_id',row['id'])
        _append(W,'ContentContainer',[{'id':cid,'guid':row.get('container_guid',f"space-container-{cid}"),
            'class':'Space','pk':row['id'],'owner_user_id':1}],src)
        _append(W,'Space',[{'guid':f"space-{row['id']}",'visibility':1,'status':1,'created_by':1,
            'contentcontainer_id':cid,**{k:v for k,v in row.items() if k!='container_guid'}}],src)
        _append(W,'SpaceMembership',[{'id':row['id'],'space_id':row['id'],'user_id':1,
            'originator_user_id':1,'status':3,'group_id':'admin'}],src)

def posts(W,rows,src=None):
    """[{id,message,content_id,container_id,state?,...}] seeds both existing rows."""
    for row in rows:
        _append(W,'Post',[{'id':row['id'],'message':row['message'],'created_by':row.get('created_by',1),
            'updated_by':row.get('created_by',1),'created_at':W.now,'updated_at':W.now}],src)
        _append(W,'Content',[{'id':row['content_id'],'guid':f"content-{row['content_id']}",
            'object_model':'post/Post','object_id':row['id'],'contentcontainer_id':row['container_id'],
            'state':row.get('state',1),'visibility':row.get('visibility',1),'pinned':False,
            'archived':False,'locked_comments':False,'created_by':row.get('created_by',1),
            'created_at':W.now,'updated_at':W.now}],src)

def comments(W,rows,src=None):
    return _append(W,'Comment',[{'object_model':'post/Post','created_by':1,'created_at':W.now,**r} for r in rows],src)

def files(W,rows,src=None):
    return _append(W,'File',[{'created_by':1,'public':False,'created_at':W.now,**r} for r in rows],src)

def notifications(W,rows,src=None):
    return _append(W,'Notification',[{'class':'TeamNotification','seen':0,'created_at':W.now,**r} for r in rows],src)

def smoke_seed(W):
    spaces(W,[{'id':10,'contentcontainer_id':10,'name':'Operations','container_guid':'ops-space',
        'description':'Internal operations collaboration'}])
    posts(W,[
        {'id':101,'content_id':201,'container_id':10,'message':
            'Policy: publish the reviewed safety checklist, then record a review comment and pin it. '
            'Keep the reference announcement text unchanged.'},
        {'id':102,'content_id':202,'container_id':10,'state':10,'message':'Safety checklist; review pending.'},
        {'id':103,'content_id':203,'container_id':10,'message':'Reference announcement; retain this wording.'},
    ])
    comments(W,[{'id':301,'object_id':101,'created_by':2,'message':'Colleague policy acknowledgment.'}])
    files(W,[{'id':401,'guid':'colleague-private','created_by':2,'file_name':'colleague.txt','size':20},
             {'id':402,'guid':'ops-private','created_by':1,'file_name':'ops.txt','size':20}])
    notifications(W,[{'id':501,'user_id':1},{'id':502,'user_id':1},{'id':503,'user_id':2}])
    steps=[
        (APP,'publish_draft',{'id':202}),
        (APP,'edit_post',{'id':102,'message':'Safety checklist reviewed and approved.'}),
        (APP,'create_comment',{'objectModel':'post/Post','objectId':102,'message':'Review recorded; checklist approved.'}),
        (APP,'pin_content',{'id':202}),
    ]
    predicates=[
        ('published','The reviewed checklist Content is published.',
         CNT(SEL(NS(APP,'Content'),AND(F('id','eq',202),F('state','eq',1)))),False),
        ('edited','The checklist Post contains approved wording.',
         CNT(SEL(NS(APP,'Post'),AND(F('id','eq',102),F('message','eq','Safety checklist reviewed and approved.')))),False),
        ('commented','The approved checklist has a review comment.',
         CNT(SEL(NS(APP,'Comment'),AND(F('object_id','eq',102),F('message','eq','Review recorded; checklist approved.')))),False),
        ('pinned','The reviewed checklist Content is pinned.',
         CNT(SEL(NS(APP,'Content'),AND(F('id','eq',202),F('pinned','eq',1)))),False),
        ('reference_unchanged','The reference announcement retains its wording.',
         CNT(SEL(NS(APP,'Post'),AND(F('id','eq',103),F('message','eq','Reference announcement; retain this wording.')))),True),
    ]
    return steps,predicates

__all__=['NEW_SERVER','spaces','posts','comments','files','notifications','smoke_seed']
