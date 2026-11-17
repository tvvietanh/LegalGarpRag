"""Pinned-checkpoint integration tests with synthetic upstream fixtures."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

from test_rule_graph import REPO, workspace, write_inputs
from test_fact_graph import cases_fixture
from test_ontology_graph import prepare as ontology_prepare, approval as make_approval, save
sys.path.insert(0, str(REPO / "src"))
from legal_graph import rule_graph as rule, ontology_graph as ontology, fact_graph as fact, integration


def prepare(root):
    _, _, _, catalog = ontology_prepare(root)
    data = write_inputs(root, cases_fixture())
    support = root / "support.py";support.write_bytes(b'#SYNTHETIC_TEST_ONLY\n')
    codes = {"support.py": rule.digest_bytes(support.read_bytes())}
    config_dir = root / "configs";config_dir.mkdir(exist_ok=True)
    config_raw = rule.canonical(rule.CONFIG).encode();(config_dir / 'rule_graph_v1.json').write_bytes(config_raw)
    rule_dir = root / "outputs/rule_graph"
    rule_result = rule.build(data);rule.export_graph(rule_result, rule_dir, config_raw=config_raw, code_hashes=codes)
    rule_nodes = {n['id']:n for n in rule_result['nodes']}
    def refresh(item):
        node=rule_nodes[item['provision_node_id']];props=node['properties']
        item['rule_node_sha256']=rule.digest(node)
        item['source_ref']={k:props[k] for k in ('source_path','source_sha256','source_record_id','source_record_sha256')}
    catalog['rule_manifest_sha256']=rule.digest_bytes((rule_dir/'manifest.json').read_bytes())
    for concept in catalog['concepts']:
        for e in concept['evidence']:refresh(e)
    for relation in catalog['taxonomy']:
        for e in relation['evidence']:refresh(e)
    catalog_path=root/'ontology/catalog.json';catalog_path.parent.mkdir(exist_ok=True);save(catalog_path,catalog)
    draft=ontology.build(data,rule_dir,catalog_path)
    ap,rp,_=make_approval(root,draft)
    approval_path=root/'ontology'/ap.name;approval_path.write_bytes(ap.read_bytes())
    review=root/'docs/milestone_2/REVIEW.md';review.parent.mkdir(parents=True);review.write_bytes(rp.read_bytes())
    ontology.export(ontology.build(data,rule_dir,catalog_path,approval_path=approval_path,review_report=review),root/'outputs/ontology_graph',codes)
    fact.export(fact.build(data,rule_dir),root/'outputs/fact_graph',codes)
    pins={'schema_version':integration.SCHEMA,'upstream_manifest_sha256':{}}
    for tag,(folder,_) in integration.BUNDLES.items():pins['upstream_manifest_sha256'][tag]=rule.digest_bytes((root/'outputs'/folder/'manifest.json').read_bytes())
    config=root/'configs/integration.json';save(config,pins)
    return config


class IntegrationTests(unittest.TestCase):
    def test_union_counts_references_and_real_traversals(self):
        with workspace() as root:
            config=prepare(root);result=integration.build(root,config)
            self.assertEqual(len(result['nodes']),11) #7Rule+3ontology+1Case
            self.assertEqual(len(result['edges']),9) #6Rule+1IS_A+2groundings
            self.assertEqual(result['coverage_report']['reviewed_case_graph_links'],0)
            self.assertEqual(result['traversal_examples']['graph_traversals'][0]['node_ids'],['ontology:concept:child','ontology:concept:parent','rule:provision:p1','rule:document:d1'])
            self.assertEqual(result['coverage_report']['candidate_source_records'],1)

    def test_stale_manifest_and_tampered_artifact_rejected(self):
        for mutation in ('manifest','nodes'):
            with workspace() as root:
                config=prepare(root)
                path=root/('outputs/fact_graph/manifest.json' if mutation=='manifest' else 'outputs/fact_graph/nodes.jsonl')
                path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaises(rule.BuildError):integration.build(root,config)

    def test_stale_current_data_code_and_config_rejected(self):
        for relative in ('Data/03_case_data/cases.jsonl','support.py','configs/rule_graph_v1.json'):
            with workspace() as root:
                config=prepare(root);path=root/relative;path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaisesRegex(rule.BuildError,'Stale'):integration.build(root,config)

    def test_stale_catalog_approval_or_review_report_rejected(self):
        for relative in ('ontology/catalog.json','ontology/approval.json','docs/milestone_2/REVIEW.md'):
            with workspace() as root:
                config=prepare(root);path=root/relative;path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaises(rule.BuildError):integration.build(root,config)

    def test_duplicate_nodes_wrong_layer_and_missing_property_references(self):
        with workspace() as root:
            result=integration.build(root,prepare(root));allowed={e['id'] for e in result['edges'] if e['layer']!='rule'}
            with self.assertRaisesRegex(rule.BuildError,'Duplicate'):integration.validate_union(result['nodes']+[result['nodes'][0]],result['edges'],allowed)
            nodes=deepcopy(result['nodes']);nodes[0]['layer']='rule' if nodes[0]['layer']!='rule' else 'ontology'
            with self.assertRaises(rule.BuildError):integration.validate_union(nodes,result['edges'],allowed)
            nodes=deepcopy(result['nodes']);next(n for n in nodes if n['type']=='Case')['properties']['document_node_id']='rule:document:missing'
            with self.assertRaisesRegex(rule.BuildError,'property reference'):integration.validate_union(nodes,result['edges'],allowed)
            nodes=deepcopy(result['nodes']);next(n for n in nodes if n['type']=='LegalConcept')['properties']['provenance'][0]['provision_node_id']='rule:provision:missing'
            with self.assertRaisesRegex(rule.BuildError,'property reference'):integration.validate_union(nodes,result['edges'],allowed)

    def test_wrong_edge_layer_endpoint_and_false_temporal_claim_rejected(self):
        with workspace() as root:
            result=integration.build(root,prepare(root));allowed={e['id'] for e in result['edges'] if e['layer']!='rule'}
            edges=deepcopy(result['edges']);next(e for e in edges if e['type']=='REGULATED_BY')['layer']='ontology'
            with self.assertRaisesRegex(rule.BuildError,'grounding'):integration.validate_union(result['nodes'],edges,allowed)
            edges=deepcopy(result['edges']);edges[0]['target_id']='missing'
            with self.assertRaisesRegex(rule.BuildError,'Dangling'):integration.validate_union(result['nodes'],edges,allowed)
            nodes=deepcopy(result['nodes']);next(n for n in nodes if n['type']=='Case')['properties']['temporal']['verified_applicability']=True
            with self.assertRaisesRegex(rule.BuildError,'temporal'):integration.validate_union(nodes,result['edges'],allowed)
            edges=deepcopy(result['edges']);edges[0]['properties']['temporal']['verified_applicability']=True
            with self.assertRaisesRegex(rule.BuildError,'temporal'):integration.validate_union(result['nodes'],edges,allowed)
            nodes=deepcopy(result['nodes']);next(n for n in nodes if n['type']=='LegalConcept')['properties']['verification']['semantic']='UNVERIFIED'
            with self.assertRaisesRegex(rule.BuildError,'Unapproved ontology'):integration.validate_union(nodes,result['edges'],allowed)

    def test_case_keyword_or_citation_not_promoted(self):
        with workspace() as root:
            result=integration.build(root,prepare(root));allowed={e['id'] for e in result['edges'] if e['layer']!='rule'}
            self.assertFalse(any(e['source_id'].startswith('fact:') for e in result['edges']))
            edge=deepcopy(next(e for e in result['edges'] if e['type']=='REGULATED_BY'))
            edge.update(id='invented',source_id='fact:case:case1',type='INSTANCE_OF',target_id='ontology:concept:parent')
            with self.assertRaisesRegex(rule.BuildError,'Case graph link'):integration.validate_union(result['nodes'],result['edges']+[edge],allowed)

    def test_diagnostics_deduplicate_copies_without_double_count(self):
        row={'id':'candidate:one','record_count':2,'value':'same'};raw=(rule.canonical(row)+'\n').encode()
        result,copies=integration.diagnostic_union({'a':{'artifacts':{'candidates.jsonl':raw}},'b':{'artifacts':{'candidates.jsonl':raw}}},'candidates.jsonl')
        self.assertEqual((len(result),result[0]['record_count'],copies),(1,2,2))
        bad={**row,'value':'conflict'}
        with self.assertRaisesRegex(rule.BuildError,'Conflicting diagnostic'):integration.diagnostic_union({'a':{'artifacts':{'candidates.jsonl':raw}},'b':{'artifacts':{'candidates.jsonl':(rule.canonical(bad)+'\n').encode()}}},'candidates.jsonl')

    def test_two_build_exports_are_identical_lf(self):
        with workspace() as root:
            config=prepare(root)
            for target in (root/'one',root/'two'):integration.export(integration.build(root,config),target,{'fixture':'hash'})
            for path in (root/'one').iterdir():self.assertEqual(path.read_bytes(),(root/'two'/path.name).read_bytes());self.assertNotIn(b'\r\n',path.read_bytes())


if __name__=='__main__':unittest.main()
