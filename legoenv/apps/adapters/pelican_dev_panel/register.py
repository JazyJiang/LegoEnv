"""Source-bound pelican_dev_panel adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='pelican_dev_panel';NEW_SERVER={APP:'pelican_dev_panel_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Node', 'Egg', 'Allocation', 'DatabaseHost', 'Role', 'Permission', 'model_has_roles', 'model_has_permissions', 'role_has_permissions']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original panel User. server_read(server) reads genuine Server.description policy. settings_rename(server,name), settings_setdescription(server,description) update own/subuser server metadata. Administrative Node/Mount/Server APIs require unavailable application realm, not fabricated. No CPU/container power, commands, real file/SFTP transfers or server provisioning executed.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='pelican_dev_panel';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('server_read', {'server': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Server',[{'id': 201, 'uuid': 'policy-server', 'name': 'Policy', 'description': 'Policy: update server202 description to Reviewed and approved. and name to Reviewed. Rename server201 to Policy reviewed. Keep Reference unchanged.', 'owner_id': 1, 'node_id': 1, 'egg_id': 1, 'allocation_id': 1}, {'id': 202, 'uuid': 'review-server', 'name': 'Pending', 'description': 'Pending review.', 'owner_id': 1, 'node_id': 1, 'egg_id': 1, 'allocation_id': 1}, {'id': 203, 'uuid': 'reference-server', 'name': 'Reference', 'description': 'Retain reference server.', 'owner_id': 1, 'node_id': 1, 'egg_id': 1, 'allocation_id': 1}])
    steps=[('__APP__', 'settings_setdescription', {'server': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'settings_rename', {'server': 202, 'name': 'Reviewed'}), ('__APP__', 'settings_rename', {'server': 201, 'name': 'Policy reviewed'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Server'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Server'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Server'),AND(F('id','eq',201),F('name','eq','Policy reviewed')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Server'),AND(F('id','eq',203),F('description','eq','Retain reference server.')))),True))
    return steps,preds
