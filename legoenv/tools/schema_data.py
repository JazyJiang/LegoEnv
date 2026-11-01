#!/usr/bin/env python3
"""Exact-range planning, chunk registration and streaming dataset assembly.

Only schema cards and generated chunks are read. This tool makes no model
requests and does not certify business consistency or research eligibility.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from schema_contract import exact_keys, generated_data, schema_card


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def read_json(path):
    if path.is_symlink():
        raise ValueError('A generated artifact must not be a symlink')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON object key')
            result[key]=value
        return result
    return json.loads(path.read_text(),object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON constant')))


def make_plan(card, prompt_sha256, identity, max_rows=200, max_cells=2000):
    schema_card(card)
    if card['status'] != 'ready':
        raise ValueError('An unconfirmed schema cannot be planned')
    if type(max_rows) is not int or type(max_cells) is not int or min(max_rows, max_cells) < 1:
        raise ValueError('Chunk budgets must be positive integers')
    if len({t['table'] for t in card['tables']}) != len(card['tables']):
        raise ValueError('Duplicate table identifier')
    tables=[]
    for index, table in enumerate(card['tables']):
        size=min(max_rows,max(1,max_cells//len(table['columns'])))
        tables.append({'index':index,'table':table['table'],'row_count':table['row_count'],
            'rows_per_chunk':size,'chunks':(table['row_count']+size-1)//size})
    plan={'format':'schema-chunks-v1','schema':card,'schema_sha256':sha(card),
        'prompt_sha256':prompt_sha256,'generator_identity':identity,
        'generator_identity_sha256':sha(identity),'max_rows':max_rows,'max_cells':max_cells,
        'tables':tables,'chunks':sum(t['chunks'] for t in tables),
        'rows':sum(t['row_count'] for t in tables),
        'contract_implementation_sha256':hashlib.sha256(Path(__file__).with_name('schema_contract.py').read_bytes()).hexdigest(),
        'planner_implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    plan['plan_sha256']=sha(plan)
    return plan


def checked_plan(path):
    plan=read_json(path)
    without={k:v for k,v in plan.items() if k!='plan_sha256'}
    if sha(without)!=plan.get('plan_sha256'):
        raise ValueError('Plan content/hash mismatch')
    rebuilt=make_plan(plan['schema'],plan['prompt_sha256'],plan['generator_identity'],plan['max_rows'],plan['max_cells'])
    if rebuilt!=plan:
        raise ValueError('Plan was produced by different settings, schema or implementation')
    return plan


def jobs(plan):
    for table in plan['tables']:
        for part in range(table['chunks']):
            start=part*table['rows_per_chunk']
            end=min(table['row_count'],start+table['rows_per_chunk'])
            yield {'job_id':'t%04d-c%08d'%(table['index'],part), 'table_index':table['index'],
                'table':table['table'],'start':start,'end':end,'row_count':end-start,
                'plan_sha256':plan['plan_sha256'],'schema_sha256':plan['schema_sha256'],
                'prompt_sha256':plan['prompt_sha256'],'generator_identity_sha256':plan['generator_identity_sha256']}


def find_job(plan, job_id):
    # A compact plan expands lazily, rather than holding all rows/chunks in RAM.
    for job in jobs(plan):
        if job['job_id']==job_id:
            return job
    raise ValueError('Unknown fixed-range job')


def validate_output(plan, job, output):
    table=copy.deepcopy(plan['schema']['tables'][job['table_index']])
    table['row_count']=job['row_count']
    card={'dataset_id':plan['schema']['dataset_id'],'tables':[table],'status':'ready'}
    generated_data(card,output)


def register(plan_path, chunk_dir, job_id, output_path):
    plan=checked_plan(plan_path)
    job=find_job(plan,job_id)
    obj=read_json(output_path)
    validate_output(plan,job,obj)
    chunk_dir.mkdir(parents=True,exist_ok=True)
    data_path=chunk_dir/(job_id+'.output.json')
    receipt_path=chunk_dir/(job_id+'.receipt.json')
    output_sha256=sha(obj)
    expected={'job':job,'output_sha256':output_sha256,'shape_verified':True}
    if receipt_path.exists():
        if read_json(receipt_path)!=expected or not data_path.is_file() or sha(read_json(data_path))!=output_sha256:
            raise ValueError('Existing chunk identity or output changed')
        return {'job_id':job_id,'skipped_identical':True,'row_count':job['row_count']}
    if data_path.exists():
        # A crash may leave a fully written payload before its receipt. Reuse
        # only identical, revalidated output; never overwrite a different one.
        if sha(read_json(data_path))!=output_sha256:
            raise ValueError('Unreceipted payload differs from supplied output')
    else:
        save(data_path,obj)
    save(receipt_path,expected)
    return {'job_id':job_id,'skipped_identical':False,'row_count':job['row_count']}


def merge(plan_path, chunk_dir, destination):
    plan=checked_plan(plan_path)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a new merged output path')
    receipts={p.name.removesuffix('.receipt.json') for p in chunk_dir.glob('*.receipt.json')}
    expected={j['job_id'] for j in jobs(plan)}
    if receipts!=expected:
        raise ValueError('Chunk coverage mismatch: missing=%d extra=%d'%(len(expected-receipts),len(receipts-expected)))
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    written=0
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=destination.parent,prefix='.'+destination.name+'.partial.',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write('{"dataset_id":'+json.dumps(plan['schema']['dataset_id'])+',"tables":[')
            for t_index, table in enumerate(plan['tables']):
                if t_index:stream.write(',')
                stream.write('{"table":'+json.dumps(table['table'])+',"rows":[')
                count=0
                for job in jobs({'tables':[table],**{k:v for k,v in plan.items() if k!='tables'}}):
                    payload=read_json(chunk_dir/(job['job_id']+'.output.json'))
                    receipt=read_json(chunk_dir/(job['job_id']+'.receipt.json'))
                    if receipt!={'job':job,'output_sha256':sha(payload),'shape_verified':True}:
                        raise ValueError('Chunk receipt/hash/identity mismatch')
                    validate_output(plan,job,payload)
                    for row in payload['tables'][0]['rows']:
                        if count:stream.write(',')
                        stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False))
                        count+=1
                if count!=table['row_count']:
                    raise ValueError('Merged row count does not match schema')
                written+=count
                stream.write(']}')
            stream.write(']}\n')
        if destination.exists():
            raise ValueError('Output appeared during merge')
        temporary.replace(destination)
        temporary=None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    # Hash in blocks: full merged data is never loaded into one object here.
    digest=hashlib.sha256()
    with destination.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return {'passed':True,'plan_sha256':plan['plan_sha256'],'dataset_id':plan['schema']['dataset_id'],
        'rows':written,'chunks':plan['chunks'],'output_bytes':destination.stat().st_size,
        'output_sha256':digest.hexdigest(),'peak_rows_loaded':max((t['rows_per_chunk'] for t in plan['tables']),default=0),
        'row_reduction_or_sampling':False,'business_consistency_verified':False,'model_requests':0}


def plan_all(cards, prompt, identity, out, max_rows, max_cells):
    out.mkdir(parents=True,exist_ok=False)
    plans, skipped=[],[]
    prompt_hash=hashlib.sha256(prompt.read_bytes()).hexdigest()
    for path in sorted(cards.glob('*.json')):
        card=read_json(path)
        if card['status']!='ready':
            skipped.append({'file':path.name,'status':card['status']})
            continue
        plan=make_plan(card,prompt_hash,identity,max_rows,max_cells)
        save(out/path.name,plan)
        plans.append({'file':path.name,'dataset_id':card['dataset_id'],'tables':len(plan['tables']),
            'rows':plan['rows'],'chunks':plan['chunks'],'plan_sha256':plan['plan_sha256']})
    summary={'planned_datasets':len(plans),'skipped_unconfirmed_datasets':len(skipped),
        'represented_rows':sum(p['rows'] for p in plans),'planned_chunks':sum(p['chunks'] for p in plans),
        'dataset_aliases_deduplicated':False,'formal_cohort_eligibility_certified':False,
        'model_requests':0,'plans':plans,'skipped':skipped}
    save(out/'PLAN_INDEX.json',summary)
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    commands=ap.add_subparsers(dest='command',required=True)
    p=commands.add_parser('plan');p.add_argument('--cards',type=Path,required=True);p.add_argument('--prompt',type=Path,required=True)
    p.add_argument('--identity',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-rows',type=int,default=200);p.add_argument('--max-cells',type=int,default=2000)
    p=commands.add_parser('job');p.add_argument('--plan',type=Path,required=True);p.add_argument('--job-id',required=True)
    p=commands.add_parser('register');p.add_argument('--plan',type=Path,required=True);p.add_argument('--job-id',required=True)
    p.add_argument('--chunks',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p=commands.add_parser('merge');p.add_argument('--plan',type=Path,required=True);p.add_argument('--chunks',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args()
    if a.command=='plan':
        result=plan_all(a.cards,a.prompt,read_json(a.identity),a.out,a.max_rows,a.max_cells)
        result={k:v for k,v in result.items() if k not in ['plans','skipped']}
    elif a.command=='job':result=find_job(checked_plan(a.plan),a.job_id)
    elif a.command=='register':result=register(a.plan,a.chunks,a.job_id,a.output)
    else:
        if a.receipt.exists():raise ValueError('Use a new merge receipt path')
        result=merge(a.plan,a.chunks,a.out)
        save(a.receipt,result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
