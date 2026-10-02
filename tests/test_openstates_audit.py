"""Audit evidence must stay deterministic, conservative and fail closed."""

import copy
from contextlib import contextmanager

import pytest
import psycopg

from opendiscourse_research.openstatesaudit import canonical, digest, disposition, permitted_identity, validate
from opendiscourse_research.openstatesaudit import audit
from opendiscourse_research.openstatesaudit import nested_dispositions
from opendiscourse_research.openstatesaudit import approval_inputs, fingerprint


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
