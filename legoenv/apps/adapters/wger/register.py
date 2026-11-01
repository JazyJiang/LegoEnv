"""wger source routines, session notes and body-weight scalar records."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wger';NEW_SERVER={APP:'routine_manager'}
CONFIG={'Account','UserProfile','Language','License','RepetitionUnit','WeightUnit','ExerciseCategory','IngredientCategory','Muscle','Equipment','Exercise','Translation','Ingredient','IngredientWeightUnit','Gym','GymConfig','GymUserConfig','GymAdminConfig','config.GymConfig','ContractType','ContractOption','Trophy'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is wger. Sign in with {p}__sign_in(username,password), as Account 1. '
    'routine_search(name,is_public,is_template,start) lists scoped routine metadata; name is an optional substring and other filters exact. routine_read(pk) reads a routine and Routine.description carries policy. '
    'routine_create(name,description,start,end) creates an owned routine; routine_update(pk,name,description,start,end) requires both dates even for text edits. '
    'day_search(routine_id) lists matching Day rows subject to the original guard. workoutsession_create(routine_id,day_id,date,notes) records a session note. '
    'workoutsession_search(routine_id) lists owned sessions; workoutsession_update(pk,routine_id,notes,date,impression) needs routine_id for its source guard and changes scalar fields only. '
    'weightentry_create(date,weight), weightentry_update(id,date,weight), weightentry_search(date) record/read owned body-weight scalars; repeated creates can collide on the runtime-generated UUID. '
    'routine_delete(pk), workoutsession_delete(pk), weightentry_delete(id) delete rows; source ownership gaps are documented. '
    'workoutlog_create upserts a WorkoutSession rather than WorkoutLog, exercise_delete only inserts DeletionLog, and stats/nutritional tools only fetch records. '
    'No full workout logging, calculation, binary media transfer or comprehensive ACL claim is made.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='wger';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('routine_search',{}),('workoutsession_search',{}),('weightentry_search',{})]
    for row in env.state.get(NS(APP,'Routine'),[]):
        if row.get('user_id')==1:reads.extend([('routine_read',{'pk':row['id']}),('day_search',{'routine_id':row['id']})])
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
def routines(W,rows,src=None):return _append(W,'Routine',[{'user_id':1,'start':'2026-10-01T00:00:00','end':'2026-10-31T00:00:00','is_template':False,'is_public':False,'fit_in_week':False,**r} for r in rows],src)
def days(W,rows,src=None):return _append(W,'Day',[{'order':1,'type':'TRAINING','is_rest':False,**r} for r in rows],src)
def sessions(W,rows,src=None):return _append(W,'WorkoutSession',[{'user_id':1,'date':'2026-10-19T09:00:00',**r} for r in rows],src)
def weights(W,rows,src=None):return _append(W,'WeightEntry',[{'user_id':1,'uuid':f"weight-{r['id']}",**r} for r in rows],src)
def smoke_seed(W):
    routines(W,[{'id':101,'name':'Review policy routine','description':'Policy: record the approved review description and session note. Keep the reference routine description unchanged.'},
        {'id':102,'name':'Review routine','description':'Review pending.'},{'id':103,'name':'Reference routine','description':'Retain this reference wording.'}])
    days(W,[{'id':201,'routine_id':101,'name':'Policy day'},{'id':202,'routine_id':102,'name':'Review day'},{'id':203,'routine_id':103,'name':'Reference day'}])
    sessions(W,[{'id':301,'routine_id':101,'day_id':201,'notes':'Existing session context.'}])
    weights(W,[{'id':401,'date':'2026-10-19T00:00:00','weight':80}])
    steps=[(APP,'routine_update',{'pk':102,'description':'Review approved and recorded.','start':'2026-10-01T00:00:00','end':'2026-10-31T00:00:00'}),
        (APP,'workoutsession_create',{'routine_id':102,'day_id':202,'date':'2026-10-22T09:00:00','notes':'Approved review recorded.'})]
    preds=[('routine','Approved routine wording recorded.',CNT(SEL(NS(APP,'Routine'),AND(F('id','eq',102),F('description','eq','Review approved and recorded.')))),False),
        ('session','Session note recorded for the review routine.',CNT(SEL(NS(APP,'WorkoutSession'),AND(F('routine_id','eq',102),F('notes','eq','Approved review recorded.')))),False),
        ('date','Session date recorded.',CNT(SEL(NS(APP,'WorkoutSession'),AND(F('routine_id','eq',102),F('date','eq','2026-10-22T09:00:00')))),False),
        ('reference','Reference description unchanged.',CNT(SEL(NS(APP,'Routine'),AND(F('id','eq',103),F('description','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','routines','days','sessions','weights','smoke_seed']
