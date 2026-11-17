"""Frozen-observation URL identity and final export tests; network is mocked."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

from test_rule_graph import REPO, workspace
from test_integration import prepare as prepare_integration
sys.path.insert(0, str(REPO / "src"))
from legal_graph import rule_graph as rule, integration, url_audit, final_release as release


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes((rule.canonical(value)+'\n').encode())


def document(root, title='SYNTHETIC LAW'):
    data=root/'Data';data.mkdir(exist_ok=True);body=b'%PDF-SYNTHETIC-UNIT-FIXTURE';(data/'local.pdf').write_bytes(body)
    return {'id':'rule:document:synthetic','type':'Document','layer':'rule','properties':{'source_properties':
            {'document_number':'01/TEST','title':title,'issuer':'SYNTHETIC AUTHORITY','metadata_verified':True,
             'source_url':'https://example.invalid/document.pdf','local_file_path':'local.pdf','local_sha256':rule.digest_bytes(body)}}}


def observation(node, header='01/TEST SYNTHETIC LAW SYNTHETIC AUTHORITY'):
    row=node['properties']['source_properties'];expected={'number':row.get('document_number') or row.get('instrument_number') or row.get('case_number') or '',
                                                         'title':row.get('title') or '', 'authority':row.get('issuer') or ''}
    evidence={'expected_source_identity':expected,'header_excerpt':header,'header_sha256':rule.digest_bytes(header.encode()),
              'source_metadata_verified':row.get('metadata_verified') is True,'local_source_sha256_match':'local_sha256' in row}
    if evidence['local_source_sha256_match']:evidence.update(local_source_path=row['local_file_path'],local_source_sha256=row['local_sha256'])
    for name,value in expected.items():
        needle=url_audit.normalize(value);evidence[name+'_match']=bool(needle and len(needle)>=4 and needle in url_audit.normalize(header))
    result={'schema_version':'url-observation-v1','document_node_id':node['id'],'document_node_sha256':rule.digest(node),
            'original_url':row['source_url'],'source_url_field':'source_url','checked_at':'2026-11-17T00:00:00+00:00',
            'http_status':200,'final_url':row['source_url'].strip(),'redirect_chain':[],'response_is_pdf':True,
            'response_sha256':row.get('local_sha256',rule.digest_bytes(b'SYNTHETIC')),'truncated':False,'identity_evidence':evidence}
    status,reasons=url_audit.classify(node,result);result.update(url_status=status,reason_codes=reasons)
    if status=='VERIFIED':result['resolved_url']=result['final_url']
    return result


def prepare(root):
    integrated_config=prepare_integration(root)
    target=root/'configs/integrated_graph_v1.json';target.write_bytes(integrated_config.read_bytes())
    result=integration.build(root,target);codes={'support.py':rule.digest_bytes((root/'support.py').read_bytes())}
    integration.export(result,root/'outputs/integrated_graph',codes)
    docs=[n for n in result['nodes'] if n['type']=='Document']
    observations=[observation(node,header='') for node in docs]
    audit=root/'audit/observations.jsonl';audit.parent.mkdir(exist_ok=True);audit.write_bytes(b''.join((rule.canonical(row)+'\n').encode() for row in observations))
    log=root/'docs/milestone_5/TEST_LOG.txt';log.parent.mkdir(parents=True);log.write_bytes(b'SYNTHETIC_TEST_LOG_ONLY\n')
    qa={'synthetic_fixture':True,'tests_passed':1,'test_failures':0,'test_errors':0,'all_219_data_hashes_match':True,
        'test_log_sha256':rule.digest_bytes(log.read_bytes()),'validated_source_sha256':codes,'dataset_digest':'SYNTHETIC_NOT_REAL_DATA'}
    qap=root/'audit/qa.json';save(qap,qa)
    baseline=root/'audit/baseline.json';save(baseline,{'commit':'SYNTHETIC_BASELINE_ONLY'})
    def pin(path):return {'path':path.relative_to(root).as_posix(),'sha256':rule.digest_bytes(path.read_bytes())}
    config={'schema_version':release.SCHEMA,'integrated_manifest':pin(root/'outputs/integrated_graph/manifest.json'),
            'url_observations':pin(audit),'qa_proof':pin(qap),'test_log':pin(log),'baseline_snapshot':pin(baseline),'upstream_reviews':[]}
    path=root/'configs/final.json';save(path,config)
    return path,config


class FinalReleaseTests(unittest.TestCase):
    def test_http200_wrong_identity_and_homepage_are_not_verified(self):
        with workspace() as root:
            node=document(root);row=observation(node,header='WRONG DOCUMENT')
            self.assertEqual(row['url_status'],'UNRESOLVED')
            row=observation(node);row['final_url']='https://example.invalid/'
            self.assertEqual(url_audit.classify(node,row)[0],'UNRESOLVED')

    def test_hash_match_without_reviewed_source_identity_is_unresolved(self):
        with workspace() as root:
            node=document(root);node['properties']['source_properties']['metadata_verified']=False
            self.assertEqual(observation(node)['url_status'],'UNRESOLVED')

    def test_mocked_blocked_and_missing_url_no_network(self):
        with workspace() as root:
            node=document(root);calls=[]
            def blocked(url):
                calls.append(url);return {'checked_at':'2026-11-17T00:00:00+00:00','access_error':'SYNTHETIC_TIMEOUT'},b''
            row=url_audit.collect_one(node,root/'Data',blocked);self.assertEqual(row['url_status'],'BLOCKED');self.assertEqual(len(calls),1)
            node['properties']['source_properties']['source_url']=''
            row=url_audit.collect_one(node,root/'Data',blocked);self.assertEqual(row['original_url'],'');self.assertEqual(row['url_status'],'BLOCKED')

    def test_resolved_url_only_if_identity_verified(self):
        with workspace() as root:
            node=document(root);row=observation(node)
            result=release.audit_rows([node],(rule.canonical(row)+'\n').encode(),root)
            self.assertEqual(result[0]['resolved_url'],row['final_url'])
            row=observation(node,header='WRONG');row['resolved_url']='https://example.invalid/wrong'
            with self.assertRaisesRegex(rule.BuildError,'status/resolution'):release.audit_rows([node],(rule.canonical(row)+'\n').encode(),root)

    def test_same_id_changed_document_context_and_snapshot_coverage_fail(self):
        with workspace() as root:
            node=document(root);row=observation(node);changed=deepcopy(node);changed['properties']['source_properties']['title']='changed same ID'
            with self.assertRaisesRegex(rule.BuildError,'Stale URL'):release.audit_rows([changed],(rule.canonical(row)+'\n').encode(),root)
            with self.assertRaises(rule.BuildError):release.audit_rows([node],b'',root)
            raw=(rule.canonical(row)+'\n').encode()
            with self.assertRaisesRegex(rule.BuildError,'Duplicate'):release.audit_rows([node],raw+raw,root)

    def test_frozen_header_flags_and_local_lineage_are_rechecked(self):
        with workspace() as root:
            node=document(root);row=observation(node);row['identity_evidence']['header_excerpt']='WRONG'
            with self.assertRaisesRegex(rule.BuildError,'flags contradict'):release.audit_rows([node],(rule.canonical(row)+'\n').encode(),root)
            row=observation(node);(root/'Data/local.pdf').write_bytes(b'changed')
            with self.assertRaisesRegex(rule.BuildError,'lineage mismatch'):release.audit_rows([node],(rule.canonical(row)+'\n').encode(),root)

    def test_independent_title_alias_review_is_snapshot_bound(self):
        with workspace() as root:
            node=document(root,title='SYNTHETIC CONSOLIDATED LAW');row=observation(node);self.assertEqual(row['url_status'],'UNRESOLVED')
            raw=(rule.canonical(row)+'\n').encode()
            approved={'document_node_id':node['id'],'decision':'APPROVED','observation_record_sha256':rule.digest(row),
                      'document_node_sha256':rule.digest(node),'response_sha256':row['response_sha256'],'expected_number':'01/TEST',
                      'reviewed_title_alias':'SYNTHETIC LAW','reviewed_authority':'SYNTHETIC AUTHORITY','evidence_quote':row['identity_evidence']['header_excerpt']}
            manual={'schema_version':'url-identity-review-v1','reviewer_role':'graph_reviewer','reviewer':'SYNTHETIC_ONLY','independent_review':True,
                    'observation_snapshot_sha256':rule.digest_bytes(raw),'approvals':[approved]}
            self.assertEqual(release.audit_rows([node],raw,root,manual)[0]['url_status'],'VERIFIED')
            manual['approvals'][0]['observation_record_sha256']='stale'
            with self.assertRaisesRegex(rule.BuildError,'Stale'):release.audit_rows([node],raw,root,manual)

    def visual_fixture(self, root):
        node=document(root);row=observation(node,header='');raw=(rule.canonical(row)+'\n').encode()
        image=root/'audit/evidence/page1.png';image.parent.mkdir(parents=True);image.write_bytes(b'\x89PNG\r\n\x1a\nSYNTHETIC_IMAGE_FIXTURE_ONLY')
        item={'document_node_id':node['id'],'decision':'APPROVED','proof_kind':'PDF_PAGE_VISUAL_IDENTITY',
              'observation_record_sha256':rule.digest(row),'document_node_sha256':rule.digest(node),'response_sha256':row['response_sha256'],
              'local_pdf_sha256':row['response_sha256'],'pdf_page_number':1,'expected_number':'01/TEST',
              'reviewed_title_alias':'SYNTHETIC LAW','reviewed_authority':'SYNTHETIC AUTHORITY',
              'transcript':'01/TEST SYNTHETIC LAW SYNTHETIC AUTHORITY','renderer':'SYNTHETIC_TEST_ONLY',
              'rendered_page_path':'audit/evidence/page1.png','rendered_page_sha256':rule.digest_bytes(image.read_bytes())}
        manual={'schema_version':'url-identity-review-v1','reviewer_role':'graph_reviewer','reviewer':'SYNTHETIC_ONLY','independent_review':True,
                'observation_snapshot_sha256':rule.digest_bytes(raw),'approvals':[item]}
        return node,raw,manual

    def test_visual_identity_positive_and_snapshot_pdf_node_page_requirements(self):
        with workspace() as root:
            node,raw,manual=self.visual_fixture(root)
            self.assertEqual(release.audit_rows([node],raw,root,manual)[0]['url_status'],'VERIFIED')
            for field,value in [('pdf_page_number',2),('pdf_page_number',True),('response_sha256','wrong'),
                                ('document_node_sha256','wrong'),('local_pdf_sha256','wrong'),('observation_record_sha256','wrong')]:
                changed=deepcopy(manual);changed['approvals'][0][field]=value
                with self.subTest(field=field,value=value):
                    with self.assertRaises(rule.BuildError):release.audit_rows([node],raw,root,changed)

    def test_visual_identity_requires_confined_matching_image_and_grounded_transcript(self):
        with workspace() as root:
            node,raw,manual=self.visual_fixture(root)
            for field,value in [('rendered_page_sha256','wrong'),('rendered_page_path','Data/local.pdf'),
                                ('transcript','unrelated title'),('renderer','')]:
                changed=deepcopy(manual);changed['approvals'][0][field]=value
                with self.subTest(field=field):
                    with self.assertRaises(rule.BuildError):release.audit_rows([node],raw,root,changed)
            changed=deepcopy(manual);changed['approvals'][0].pop('rendered_page_sha256')
            with self.assertRaises(rule.BuildError):release.audit_rows([node],raw,root,changed)

    def test_final_build_keeps_graph_bytes_and_is_deterministic_offline(self):
        with workspace() as root:
            config,_=prepare(root)
            for folder in (root/'one',root/'two'):
                artifacts,deps,quality=release.build(root,config)
                self.assertEqual(artifacts['nodes.jsonl'],(root/'outputs/integrated_graph/nodes.jsonl').read_bytes())
                self.assertEqual(artifacts['edges.jsonl'],(root/'outputs/integrated_graph/edges.jsonl').read_bytes())
                release.export(artifacts,deps,quality,folder,{'fixture':'hash'})
            for path in (root/'one').iterdir():self.assertEqual(path.read_bytes(),(root/'two'/path.name).read_bytes());self.assertNotIn(b'\r\n',path.read_bytes())

    def test_stale_audit_and_qa_source_proof_fail(self):
        with workspace() as root:
            config,values=prepare(root);path=root/values['url_observations']['path'];path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(rule.BuildError,'Stale pinned'):release.build(root,config)
        with workspace() as root:
            config,values=prepare(root);path=root/values['qa_proof']['path'];qa=json.loads(path.read_bytes());qa['validated_source_sha256']['support.py']='stale';save(path,qa)
            values['qa_proof']['sha256']=rule.digest_bytes(path.read_bytes());save(config,values)
            with self.assertRaisesRegex(rule.BuildError,'QA source/test snapshot stale'):release.build(root,config)


if __name__=='__main__':unittest.main()
