"""Source-bound registration; no invented tool or authentication implementation."""
import copy,json
import packlib,runtime
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='relate'
CFG={'order': 118, 'entity': 'Participation', 'pk': 'id', 'field': 'notes', 'field_arg': 'notes', 'id_arg': 'participation_id', 'write_tool': 'participation_edit', 'update_extra': {'course_identifier': 'intro-cs'}, 'reads': [['participation_query', {'course_identifier': 'intro-cs', 'queries': 'active'}]], 'carrier': 'notes_field', 'login_tool': 'user_sign_in_by_user_pw', 'user_arg': 'username', 'exec_binding_fixes': [{'tool': 'participation_edit', 'path': ['exec_spec', 'key'], 'value': {'id': {'$arg': 'participation_id'}}, 'reason': 'Declared participation_id and original target precondition identify Participation.id; correct the upsert key from undeclared participation_id column to actual id.', 'source_evidence': ['entities.Participation.columns.id', 'input_schema.participation_id', 'guards.preconditions[0][0]']}, {'tool': 'participation_query', 'path': ['exec_spec', 'scope', 'where', 'course_id'], 'value': {'$ref': {'entity': 'Course', 'where': {'identifier': {'$arg': 'course_identifier'}}, 'col': 'id'}}, 'reason': 'Source course/enrollment.py:627 explicitly Participation.objects.filter(course); original target/member guards already resolve Course.identifier=course_identifier to Course.id. Replace wrong user-account scope with that exact source Course binding.', 'source_evidence': ['_evidence.locator=course/enrollment.py:627', '_evidence.ref_code:Participation.objects.filter(course).filter(q)', 'guards.preconditions[0][0].select.where.args[1].value.select Course.identifier']}], 'notes': '{p}__ user_sign_in_by_user_pw(username,password). participation_query(course_identifier,queries) reads native Participation.notes; participation_edit(participation_id,course_identifier,notes) edits that row. Existing source memberships are retained; fresh normal students add no instructor rights. Course binding follows exact source filter(course) and existing guard resolution; active-member rather than instructor permission is retained.', 'limitations': ['Only Participation.notes updates and native note readback certified. No quiz content, grading, flow evaluation, examination tickets, code execution or email/network effects executed.', 'Original actor course memberships/instructor-student role strings are retained. Four additional ordinary student fixture users/participations follow the existing student shape and unique user/course keys; no new privileged role or source guard is introduced.', 'Original update guard requires an active participation, not instructor role. Query scope fixes the compiler account-id mismatch using exact source ORM filter(course) and the same original Course.identifier guard lookup. No extra role check or full query-language semantics is claimed.', 'Repair only source-proven upsert target alias and copy the already declared fields mapping into supported set_on_exists so undeclared routing arguments are not written into rows.'], 'app': 'relate', 'account_entity': 'User', 'account_user_col': 'username', 'account_password_col': 'password', 'argument_ids': {}, 'fixture_rows': [{'id': 201, 'user_id': 1001, 'course_id': 10, 'role': 'student', 'status': 'active', 'notes': 'Pending 1'}, {'id': 202, 'user_id': 1002, 'course_id': 10, 'role': 'student', 'status': 'active', 'notes': 'Pending 2'}, {'id': 203, 'user_id': 1003, 'course_id': 10, 'role': 'student', 'status': 'active', 'notes': 'Pending 3'}, {'id': 204, 'user_id': 1004, 'course_id': 10, 'role': 'student', 'status': 'active', 'notes': 'Policy: update the three queued records; retain this reference record unchanged.'}], 'updates': [[201, 'Approved first.'], [202, 'Approved second.'], [203, 'Approved third.']], 'protected': [204, 'Policy: update the three queued records; retain this reference record unchanged.'], 'policy_text': 'Policy: update the three queued records; retain this reference record unchanged.', 'original_memberships': [{'id': 20, 'user_id': 1, 'course_id': 10, 'role': 'instructor', 'status': 'active'}, {'id': 21, 'user_id': 2, 'course_id': 10, 'role': 'student', 'status': 'active'}], 'fixture_student_users': [{'id': 1001, 'username': 'learner1001@relate.example', 'password': 'pw-peer', 'email': 'learner1001@relate.example', 'first_name': 'Bob', 'last_name': 'Builder', 'is_active': True, 'is_staff': False, 'name_verified': True, 'status': 'active', 'editor_mode': 'default', 'institutional_id_verified': False}, {'id': 1002, 'username': 'learner1002@relate.example', 'password': 'pw-peer', 'email': 'learner1002@relate.example', 'first_name': 'Bob', 'last_name': 'Builder', 'is_active': True, 'is_staff': False, 'name_verified': True, 'status': 'active', 'editor_mode': 'default', 'institutional_id_verified': False}, {'id': 1003, 'username': 'learner1003@relate.example', 'password': 'pw-peer', 'email': 'learner1003@relate.example', 'first_name': 'Bob', 'last_name': 'Builder', 'is_active': True, 'is_staff': False, 'name_verified': True, 'status': 'active', 'editor_mode': 'default', 'institutional_id_verified': False}, {'id': 1004, 'username': 'learner1004@relate.example', 'password': 'pw-peer', 'email': 'learner1004@relate.example', 'first_name': 'Bob', 'last_name': 'Builder', 'is_active': True, 'is_staff': False, 'name_verified': True, 'status': 'active', 'editor_mode': 'default', 'institutional_id_verified': False}]}
NEW_SERVER={APP:APP+'_records'};NEW_CONTENT={APP:[CFG['entity']]}
NEW_NOTES={APP:CFG['notes']}
LOGIN={APP:(CFG['login_tool'],CFG['user_arg'])} if CFG.get('login_tool') else {}
SERVER.update(NEW_SERVER);PFX[APP]=APP;CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
def _signin(env,W):
    if not CFG.get('login_tool'):return None
    args={CFG['user_arg']:W.persona,CFG.get('password_arg','password'):W.password};args.update(CFG.get('login_extra',{}))
    return env.call(NS(APP,CFG['login_tool']),args)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    if CFG.get('login_tool'):
        result=_signin(env,self);assert result.get('ok'),result
    for tool,args in CFG.get('reads',[]):
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=copy.deepcopy(rows);assert all(isinstance(r['id'],int) for r in rows);W.seed(APP,entity,rows,src=src);return rows
def smoke_seed(W):
    W.spec[APP]['seed_state']['User'].extend(copy.deepcopy(CFG['fixture_student_users']))
    records(W,CFG['entity'],copy.deepcopy(CFG['original_memberships'])+CFG['fixture_rows'])
    steps=[];preds=[]
    for i,(identifier,value) in enumerate(CFG['updates']):
        args=dict(CFG.get('update_extra',{}));args[CFG['id_arg']]=CFG.get('argument_ids',{}).get(str(identifier),identifier)
        if CFG.get('field_arg'):args[CFG['field_arg']]=value
        steps.append((APP,CFG['write_tool'],args))
        preds.append(('updated_'+str(i),'Native field changed on requested record.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',identifier),F(CFG['field'],'eq',value)))),False))
    keep=CFG['protected'];preds.append(('protected','Reference record retains its original field.',CNT(SEL(NS(APP,CFG['entity']),AND(F(CFG['pk'],'eq',keep[0]),F(CFG['field'],'eq',keep[1])))),True))
    if CFG.get('password_arg','password')!='password' and CFG.get('login_tool'):
        raw=steps;steps=[lambda env:_signin(env,W)]+[(lambda env,t=t,a=a:env.call(NS(APP,t),a)) for _,t,a in raw]
    return steps,preds
