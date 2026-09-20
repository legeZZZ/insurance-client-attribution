"""Validate research records against the existing in-memory registry only."""
import json,pathlib,sys,collections,hashlib
p=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(p.parent/'可执行代码包'))
from track2_v5.factor_registry import FactorRegistry
factors=json.loads((p/'候选因子库.json').read_text())
sources={s['source_id']:s for s in json.loads((p/'研究来源.json').read_text())}
old=json.loads((p/'现有因子盘点.json').read_text())
ids=[f['factor_id'] for f in factors]
assert len(ids)==len(set(ids))==38
assert not set(ids)&{f['factor_id'] for f in old['named_factors']}
r=FactorRegistry(':memory:')
for f in factors:
 assert f['status']=='research_candidate' and f['license_ref'] is None
 m=f['metadata']
 for k in ['formula','scope','data_source','validation','failure_mode','time_contract','causal_role','source_ids']: assert m[k]
 assert all(s in sources for s in m['source_ids'])
 assert m['production_ready'] is False and m['business_effect_verified'] is False
 r.register_factor(f)
 assert r.get_factor(f['factor_id'])['metadata']==m
assert r.retrieve_factor_candidates('',limit=100)==[]
assert r.connection.execute('SELECT count(*) FROM snapshots').fetchone()[0]==0
assert r.connection.execute('SELECT count(*) FROM evidence').fetchone()[0]==0
r.close()
result={'status':'PASS','candidate_count':len(ids),'source_count':len(sources),'existing_named_count':old['named_count'],'existing_series_count':old['series_definition_count'],'family_counts':dict(collections.Counter(f['metadata']['family'] for f in factors)),'checks':['unique IDs','no ID collision with audited 49 definitions','complete source references','existing FactorRegistry in-memory round-trip','no candidate returned by default active retrieval','zero fabricated snapshots','zero business observation evidence','no production DB writes'],'not_verified':['source data availability','production authorization','measurement validity','business effects','causal identification','deduplication against all historical runtime databases'],'sha256':{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['候选因子库.json','研究来源.json','现有因子盘点.json']}}
(p/'校验结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
