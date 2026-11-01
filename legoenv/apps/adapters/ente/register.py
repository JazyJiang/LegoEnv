'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound ente adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ente';NEW_SERVER={APP:'ente_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Token']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses existing spec equality login on encrypted_email. collection_get_by_id(collectionID) exposes only collection metadata; no readable plaintext policy carrier exists. Collection create/rename/trash mutate opaque metadata independently; complete admission blocked. No encryption/decryption/SRP/binary files/network effects implemented.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='ente';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('collection_get_by_id', {'collectionID': 201}), ('collection_get', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source-readable business policy text carrier; do not fabricate a read tool or repurpose metadata as instructions. Complete admission blocked.')
def metadata_smoke_seed(W):
    records(W,'Collection',[{'id': 201, 'collection_id': 201, 'owner_id': 1, 'name': 'Operations', 'encrypted_key': 'ck', 'key_decryption_nonce': 'kn', 'type': 'album', 'attributes': {}, 'app': 'photos', 'is_deleted': False}, {'id': 202, 'collection_id': 202, 'owner_id': 1, 'name': 'Review', 'encrypted_key': 'ck', 'key_decryption_nonce': 'kn', 'encrypted_name': 'old-name', 'type': 'album', 'attributes': {}, 'app': 'photos', 'is_deleted': False}, {'id': 203, 'collection_id': 203, 'owner_id': 1, 'name': 'Reference', 'encrypted_key': 'ck', 'key_decryption_nonce': 'kn', 'type': 'album', 'attributes': {}, 'app': 'photos', 'is_deleted': False}])
    steps=[('__APP__', 'collection_rename', {'collectionID': 202, 'encryptedName': 'reviewed-opaque', 'nameDecryptionNonce': 'n2'}), ('__APP__', 'collection_create', {'name': 'Approved', 'encryptedKey': 'ck', 'keyDecryptionNonce': 'kn', 'type': 'album', 'attributes': {}}), ('__APP__', 'collection_trashv3', {'collectionID': 201, 'keepFiles': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_id','eq',202),F('encrypted_name','eq','reviewed-opaque')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('name','eq','Approved'),F('owner_id','eq',1)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_id','eq',201),F('is_deleted','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Collection'),AND(F('collection_id','eq',203),F('name','eq','Reference')))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
