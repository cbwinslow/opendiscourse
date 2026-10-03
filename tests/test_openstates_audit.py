"""Audit evidence must stay deterministic, conservative and fail closed."""

import copy
from contextlib import contextmanager

import psycopg
import pytest

from opendiscourse_research.openstatesaudit import (
    approval_inputs,
    audit,
    canonical,
    coverage_plans,
    digest,
    disposition,
    fingerprint,
    nested_dispositions,
    permitted_identity,
    schema_review,
    semantic_mapping,
    validate,
)


def complete():
    report={'errors': [], 'mapping_version':'openstates-audit-1','relations':[{'source_schema':'public','source_table':'person','relkind':'r'}],
            'columns':[{'source_schema':'public','source_table':'person','source_path':'id','source_type':'text'}],
            'nested_fields':[{'source_schema':'public','source_table':'person','source_path':[{'kind':'column','value':'extras'},{'kind':'key','value':'party'}],'source_type':'string'}],
            'keys':[], 'fdw':[], 'fdw_columns':[], 'approval_evidence':{},
            'registered_candidate_artifacts':[{'artifact_id':'fixture','artifact_key':'fixture','checksum_sha256':'a'*64,'bytes_downloaded':10}]}
    stamp(report)
    return report


def stamp(report):
    value=fingerprint(report)
    mapping={'schema':1,'kind':'mapping_review','decision':'approved','mapping_version':report['mapping_version'],
             'structural_sha256':value['structural_sha256'],'mapping_sha256':value['mapping_sha256'],
             'reviewer':'isolated test fixture','reviewed_at':'2026-10-02T00:00:00Z'}
    restore={'schema':1,'kind':'restore_attestation','decision':'verified','structural_sha256':value['structural_sha256'],
             **report['registered_candidate_artifacts'][0], 'record_validated':True,'record_sha256':'b'*64,
             'attested_by':'isolated test fixture','restored_at':'2026-10-02T00:00:00Z'}
    report['approval_evidence']=approval_inputs(report,mapping,restore)
    report['fingerprint']=fingerprint(report)


def test_deterministic_serialization():
    assert canonical({'b': 2, 'a': 1}) == canonical({'a': 1, 'b': 2})
    assert digest({'b': 2, 'a': 1}) == digest({'a': 1, 'b': 2})


@pytest.mark.parametrize('field,new_value', [('relations', {'source_schema':'public','source_table':'new','relkind':'r'}),
                                         ('columns', {'source_schema':'public','source_table':'person','source_path':'new','source_type':'text'}),
                                         ('nested_fields', {'source_schema':'public','source_table':'person','source_path':[{'kind':'column','value':'extras'},{'kind':'key','value':'new'}],'source_type':'string'})])
def test_unreviewed_structural_drift_rejected(field, new_value):
    baseline = complete()
    changed = copy.deepcopy(baseline)
    changed[field].append(new_value)
    with pytest.raises(ValueError,match='recomputed'):
        validate(changed,baseline)
    stamp(changed)
    with pytest.raises(ValueError, match='drift'):
        validate(changed, baseline)


@pytest.mark.parametrize('gap', ['measurement', 'lineage', 'review'])
def test_incomplete_evidence_fails_closed(gap):
    report = complete()
    if gap == 'measurement':
        report['errors'] = [{'scope': 'person count', 'status': 'unresolved', 'sqlstate': '57014'}]
    elif gap == 'lineage':
        report['approval_evidence'].pop('restore')
    else:
        report['approval_evidence'].pop('mapping')
    report['fingerprint']=fingerprint(report)
    with pytest.raises(ValueError):
        validate(report)


def test_explicit_complete_fixture_passes_and_measurement_changes_are_not_schema_drift():
    report=complete()
    validate(report,copy.deepcopy(report))
    changed=copy.deepcopy(report)
    changed['relations'][0]['row_count']=23
    changed['fingerprint']=fingerprint(changed)
    validate(changed,report)
    assert changed['fingerprint']['structural_sha256']==report['fingerprint']['structural_sha256']
    assert changed['fingerprint']['measurements_sha256']!=report['fingerprint']['measurements_sha256']


def test_name_collision_never_resolves_person():
    people = [('openstates', 'ocd-person/one', 'Same Name'), ('openstates', 'ocd-person/two', 'Same Name')]
    assertions = [permitted_identity(namespace, identifier) for namespace, identifier, _ in people]
    assert assertions[0] != assertions[1]
    assert permitted_identity('name', 'Same Name') is None
    assert permitted_identity('fec-committee', 'C000001') is None
    assert permitted_identity('bioguide', 'A000001') == ('bioguide', 'A000001')


@pytest.mark.parametrize('name,expected', [('auth_user', 'implementation_only'),
    ('profiles_profile', 'implementation_only'), ('opencivicdata_billversion', 'retain_source_only'),
    ('openstates_personoffice', 'retain_source_only'), ('boundaries_boundary', 'reference_only'),
    ('v1_legacybillmapping', 'reference_only'), ('unknown_table', 'unresolved')])
def test_sensitive_and_unknown_relations_never_sampled(name, expected):
    assert disposition({'source_table': name, 'extension': None, 'relkind': 'r'})['disposition'] == expected


def test_sequence_is_catalog_only():
    assert disposition({'source_table': 'opencivicdata_id_seq', 'extension': None, 'relkind': 'S'})['disposition'] == 'implementation_only'


def test_nested_null_rate_uses_mixed_array_occurrences_not_parent_sql_nulls():
    fields = [{'source_schema':'public', 'source_table':'person', 'source_path':['extras','[]'],
               'source_type':kind, 'occurrence_count':count, 'null_rate':0.2}
              for kind,count in [('string',3),('null',1)]]
    columns = [{'source_schema':'public','source_table':'person','source_path':'extras','null_rate':0.2}]
    corrected = nested_dispositions(fields,columns)
    assert all(f['null_rate']==0.25 for f in corrected)
    assert all(f['source_column_sql_null_rate']==0.2 for f in corrected)
    assert all(f['null_rate_scope']=='present_path_occurrences; absent paths are not nulls' for f in corrected)
    assert fields[0]['null_rate']==0.2


def test_permission_failure_is_retained_and_later_measurements_run():
    class DeniedReader:
        @contextmanager
        def snapshot(self):
            yield 'test-only'

        def namespaces(self,schema):
            return self.query('identity')

        def identity_counts(self,schema):
            return []
        def query(self, name, params=()):
            if name == 'catalog':
                return [{'source_schema': 'public', 'source_table': 'opencivicdata_person',
                         'extension': None, 'relkind': 'r', 'selectable': False}]
            if name == 'columns':
                return [{'source_schema': 'public', 'source_table': 'opencivicdata_person',
                         'source_path': 'id', 'source_type': 'text'}]
            if name == 'identity':
                return [{'namespace': 'ocd-person', 'identifier_count': 1}]
            return []

        def table_profile(self, *args):
            raise psycopg.errors.InsufficientPrivilege('private server message must not be published')

        def version(self):
            return '17'

        def samples(self, *args):
            return []

    checkpoints = []
    report = audit(DeniedReader(), DeniedReader(), ['public'], checkpoint=lambda phase, item: checkpoints.append((phase, item)))
    assert report['errors'][0]['sqlstate'] == '42501'
    assert report['relations'][0]['row_count'] is None
    assert report['relations'][0]['fdw_status'] == 'present_but_unreadable'
    assert report['identity']['namespaces'][0]['identifier_count'] == 1
    assert 'private server message' not in canonical(report)
    assert checkpoints[0][0] == 'catalog'
    assert all(not evidence['reuse_allowed'] for _, evidence in checkpoints)
    with pytest.raises(ValueError, match='incomplete'):
        validate(report)


def test_parent_path_keeps_session_and_names_unmeasured_alternate():
    columns = {
        ('public', 'action'): {'id', 'bill_id'},
        ('public', 'bill'): {'id', 'legislative_session_id'},
        ('public', 'session'): {'id', 'jurisdiction_id'},
        ('public', 'organization'): {'id', 'jurisdiction_id'},
    }
    edges = {
        ('public', 'action'): [
            {'constraint_name': 'action_bill', 'column': 'bill_id', 'target_schema': 'public', 'target_table': 'bill', 'target_column': 'id'},
            {'constraint_name': 'action_org', 'column': 'organization_id', 'target_schema': 'public', 'target_table': 'organization', 'target_column': 'id'},
        ],
        ('public', 'bill'): [
            {'constraint_name': 'bill_session', 'column': 'legislative_session_id', 'target_schema': 'public', 'target_table': 'session', 'target_column': 'id'},
        ],
    }
    plan = coverage_plans('public', 'action', columns, edges)[0]
    assert plan['method'] == 'parent_derived'
    assert plan['dimensions'][0]['name'] == 'legislative_session_id'
    assert plan['dimensions'][1]['name'] == 'jurisdiction_id'
    assert plan['alternate_paths'][0]['measured'] is False
    assert coverage_plans('public', 'note', {('public', 'note'): {'id'}}, {})[0]['method'] == 'unavailable'
    jurisdiction = coverage_plans('public', 'opencivicdata_jurisdiction', {('public', 'opencivicdata_jurisdiction'): {'id'}}, {})[0]
    assert jurisdiction['jurisdiction_coverage'] == 'own_source_key'
    assert jurisdiction['session_coverage'] == 'not_supplied'
    session = coverage_plans('public', 'opencivicdata_legislativesession', {('public', 'opencivicdata_legislativesession'): {'id', 'jurisdiction_id'}}, {})[0]
    assert [item['name'] for item in session['dimensions']] == ['id', 'jurisdiction_id']


def test_schema_review_states_bill_constraint_without_copying_the_table():
    relation = {'source_schema': 'public', 'source_table': 'opencivicdata_bill', 'owned_target': 'core.bill',
                'disposition': 'promote_typed', 'fdw_status': 'present_but_unreadable', 'reader_change': 'separate reviewed approval required'}
    owned = [{'source_schema': 'core', 'source_table': 'bill', 'source_path': name, 'source_type': 'text'}
             for name in ('ocd_id', 'title', 'bill_type', 'bill_number')]
    mapped = semantic_mapping(relation, {'source_path': 'id'}, owned)
    assert mapped['owned_target'] == 'core.bill.ocd_id'
    assert 'bill_type' in mapped['transform']
    assert semantic_mapping(relation, {'source_path': 'identifier'}, owned)['disposition'] == 'retained_source_detail'
    review = schema_review([relation], owned)[0]
    assert review['table_copy'] is False
    assert review['target_status'] == 'present'
    assert any('NOT NULL' in item for item in review['needed_changes'])
    assert schema_review([relation], None)[0]['target_status'] == 'unresolved'


def test_resume_reuses_measurements_only_for_the_same_catalog_baseline():
    class CountingReader:
        def __init__(self):
            self.profiles = 0

        @contextmanager
        def snapshot(self):
            yield 'test-only'

        def query(self, name, params=()):
            if name == 'catalog':
                return [{'source_schema': 'public', 'source_table': 'opencivicdata_person', 'extension': None, 'relkind': 'r'}]
            if name == 'columns':
                return [{'source_schema': 'public', 'source_table': 'opencivicdata_person', 'source_path': 'id', 'source_type': 'text'}]
            return []

        def table_profile(self, *args):
            self.profiles += 1
            return {'row_count': 4, 'null_0': 1}

        def samples(self, *args):
            return [{'id': 'person-1'}]

        def version(self):
            return '17'

        def namespaces(self, schema):
            return []

        def identity_counts(self, schema):
            return []

    source, warehouse = CountingReader(), CountingReader()
    checkpoints = []
    report = audit(source, warehouse, ['public'], checkpoint=lambda phase, item: checkpoints.append((phase, item)))
    assert source.profiles == 1
    assert report['coverage'][0]['method'] == 'unavailable'
    assert report['coverage'][0]['observed_groups'] is None
    assert report['resume_status'] == 'not_requested'
    source.profiles = 0
    reused = audit(source, warehouse, ['public'], prior=checkpoints)
    assert source.profiles == 0
    assert reused['relations'][0]['row_count'] == 4
    assert reused['resume_status'] == 'reused_same_snapshot_baseline'
    rejected_prior = [(phase, {**evidence, 'catalog_baseline': 'different'}) for phase, evidence in checkpoints]
    source.profiles = 0
    rejected = audit(source, warehouse, ['public'], prior=rejected_prior)
    assert source.profiles == 1
    assert rejected['resume_status'] == 'rejected_different_snapshot_baseline'
    blocked = [(phase, {**evidence, 'reuse_allowed': False}) for phase, evidence in checkpoints]
    source.profiles = 0
    retried = audit(source, warehouse, ['public'], prior=blocked)
    assert source.profiles == 1
    assert retried['errors'] == []
    assert retried['resume_status'] == 'no_reusable_success'
