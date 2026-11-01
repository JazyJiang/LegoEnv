"""Calibre scalar-library attachment, with neutral calibre namespace."""
import json
import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = 'calibre'
NEW_SERVER = {APP:'library'}
NEW_CONTENT = {APP:[
    'Book','Author','BookAuthorLink','Publisher','BookPublisherLink','Tag','BookTagLink',
    'Series','BookSeriesLink','Rating','BookRatingLink','Format','Cover','Comment',
    'Language','BookLanguageLink','BookIdentifier','BookPagesLink','CustomColumn',
    'BookPluginData','ConversionOption','Preference','LastReadPosition','Annotation',
    'AnnotationDirtied','MetadataDirtied','Note','NoteResource','NoteResourceLink',
]}
NEW_NOTES = {APP:(
    '{p}__ is the e-book library. Sign in using {p}__sign_in(name=<your email>,password); '
    'you are writable User 1. list_books(search) and search_books(query) return Book scalar '
    'rows; optional case-insensitive substrings search title/author_sort, and omitted search '
    'lists all books. get_book(book_id) reads one integer-id Book row. '
    'set_book_fields(book_id,title,author_sort,series_index) updates scalar metadata. '
    'add_book(filename,add_duplicates,title,body) creates only a Book title row; '
    'it does not import file bytes, formats or nested authors/tags. '
    'delete_book(book_ids=<one integer>) deletes one book; comma-separated batches are unsupported. '
    'get_note(field,item_id) reads category-item notes, for example field=authors and an '
    'author id supplied by the task; there is no note/category list interface. '
    'set_note(field,item_id,html,searchable_text) creates or replaces the same item note. '
    'set_last_read_position(book_id,fmt,device,cfi,pos_frac) updates your reading progress; '
    'get_last_read_position(book_id,fmt) reads your rows. get_annotations(book_id,fmt) '
    'reads only your seeded annotations. Legacy encoded which selectors are not parsed. '
    'set_book_cover(book_id,cover_data) upserts Cover.data, without changing Book.has_cover. '
    'Other source endpoints have limited executors: full-text search indexes, category joins, '
    'field maps, UUID/batch selectors, cross-library copy/move, file transfers and full '
    'annotation-map merge are not implemented. Use the verified scalar interfaces above.'
)}
LOGIN = {APP:('sign_in','name')}
SERVER.update(NEW_SERVER)
PFX[APP] = 'calibre'
CONTENT.update(NEW_CONTENT)
NOTES.update(NEW_NOTES)
packlib.LOGIN.update(LOGIN)

OBS_READS = ['list_books','search_books','opds_catalog','recently_added_books','get_last_read_position','get_annotations','get_note']
_original_obs = World.obs_report

def _obs_report(self):
    rep,bad = _original_obs(self)
    if APP not in self.apps:
        return rep,bad
    env = runtime.Env(self.world)
    result = env.call(NS(APP,'sign_in'),{'name':self.persona,'password':self.password})
    if not result.get('ok'):
        raise RuntimeError(f'Calibre observation login failed: {result}')
    reads = [(tool,{}) for tool in OBS_READS if tool!='get_note']
    reads += [('get_note',{'field':r['colname'],'item_id':r['item']})
              for r in env.state.get(NS(APP,'Note'),[])]
    for tool,args in reads:
        result = env.call(NS(APP,tool),args)
        if not result.get('ok'):
            raise RuntimeError(f'Calibre observation {tool} failed: {result}')
        key = f'{APP} {tool}' + (f" {args['field']}:{args['item_id']}" if args else '')
        rep[key] = len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{key:size for key,size in rep.items() if size>OBS_CAP}

World.obs_report = _obs_report

def _append(W,entity,rows,src=None):
    rows = [dict(row) for row in rows]
    for row in rows:
        if not isinstance(row.get('id'),int) or isinstance(row['id'],bool):
            raise ValueError(f'{entity} seed ids must be integers')
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:
        W.bindings[NS(APP,entity)] = {'dataset':src,'rows':len(rows)}
    return rows

def books(W,rows,src=None):
    return _append(W,'Book',[{'series_index':1.0,'timestamp':W.now,'last_modified':W.now,**r} for r in rows],src)

def authors(W,rows,src=None):
    return _append(W,'Author',rows,src)

def notes(W,rows,src=None):
    """[{id,item,colname,doc,searchable_text?}] for real category-item notes."""
    return _append(W,'Note',[{'searchable_text':r.get('doc',''),**r} for r in rows],src)

def reading_positions(W,rows,src=None):
    return _append(W,'LastReadPosition',[{'user':W.persona,'format':'epub','device':'web-reader',
        'cfi':'epubcfi(/6/2)','epoch':0.0,'pos_frac':0.0,**r} for r in rows],src)

def covers(W,rows,src=None):
    return _append(W,'Cover',rows,src)

def annotations(W,rows,src=None):
    return _append(W,'Annotation',[{'user':W.persona,'user_type':'web','format':'epub',
        'timestamp':0.0,'annot_type':'note','searchable_text':'',**r} for r in rows],src)

def smoke_seed(W):
    books(W,[
        {'id':101,'title':'Harbor Field Guide','author_sort':'Harbor Editorial'},
        {'id':102,'title':'Practical Map Reading','author_sort':'Harbor Editorial'},
        {'id':103,'title':'Reserved Archive Atlas','author_sort':'Archive Desk'},
    ])
    authors(W,[{'id':11,'name':'Harbor Editorial'},{'id':12,'name':'Archive Desk'}])
    _append(W,'BookAuthorLink',[{'id':501,'book':101,'author':11},
        {'id':502,'book':102,'author':11},{'id':503,'book':103,'author':12}])
    notes(W,[
        {'id':201,'item':11,'colname':'authors','doc':
            'Policy: label reviewed editions as revised and record the review in the author note. '
            'The Reserved Archive Atlas title must remain unchanged.'},
        {'id':202,'item':12,'colname':'authors','doc':'Archive review pending.'},
    ])
    reading_positions(W,[{'id':301,'book':101,'pos_frac':0.1}])
    covers(W,[{'id':401,'book':101,'data':{'asset':'old-cover'}}])
    annotations(W,[{'id':601,'book':101,'annot_id':'reading-note-1','annot_data':{'text':'Review opening chapter.'}}])
    steps = [
        (APP,'set_book_fields',{'book_id':101,'title':'Harbor Field Guide, revised'}),
        (APP,'set_note',{'field':'authors','item_id':12,'html':'Archive review completed; reference title retained.','searchable_text':'Archive review completed'}),
        (APP,'set_last_read_position',{'book_id':101,'fmt':'epub','device':'web-reader','cfi':'epubcfi(/6/20)','pos_frac':0.5}),
        (APP,'set_book_cover',{'book_id':101,'cover_data':{'asset':'revised-cover'}}),
    ]
    predicates = [
        ('retitled','The reviewed guide title is revised.',
         CNT(SEL(NS(APP,'Book'),AND(F('id','eq',101),F('title','eq','Harbor Field Guide, revised')))),False),
        ('noted','The existing archive author note records its completed review.',
         CNT(SEL(NS(APP,'Note'),AND(F('item','eq',12),F('colname','eq','authors'),
             F('doc','eq','Archive review completed; reference title retained.')))),False),
        ('progress','The existing reading position is updated to one half.',
         CNT(SEL(NS(APP,'LastReadPosition'),AND(F('book','eq',101),F('user','eq',W.persona),
             F('pos_frac','eq',0.5),F('cfi','eq','epubcfi(/6/20)')))),False),
        ('covered','The existing cover stores the revised asset.',
         CNT(SEL(NS(APP,'Cover'),AND(F('book','eq',101),F('data.asset','eq','revised-cover')))),False),
        ('reserved_unchanged','The reserved reference title remains unchanged.',
         CNT(SEL(NS(APP,'Book'),AND(F('id','eq',103),F('title','eq','Reserved Archive Atlas')))),True),
    ]
    return steps,predicates

__all__ = ['NEW_SERVER','books','authors','notes','reading_positions','covers','annotations','smoke_seed']
