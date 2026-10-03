"""Exercise audit SQL only against an isolated mutation-capable test database."""

import os
import uuid

import psycopg
import pytest
from psycopg import sql

from opendiscourse_research.openstatesaudit import audit, canonical
from opendiscourse_research.repositories.openstates_audit import (
    Reader,
    RowFilteringError,
)

pytestmark = pytest.mark.db


@pytest.fixture(scope='module')
def audit_database():
    dsn = os.environ.get('OPENDISCOURSE_TEST_DATABASE_URL')
    container = None
    if not dsn:
        postgres = pytest.importorskip('testcontainers.postgres')
        container = postgres.PostgresContainer('postgres:17', dbname='test')
        container.start()
        dsn = container.get_connection_url().replace('postgresql+psycopg2://', 'postgresql://')
    with psycopg.connect(dsn) as conn:
        database = conn.execute('SELECT current_database()').fetchone()[0]
        if database in ('openstates', 'opendiscourse'):
            pytest.fail('Refusing mutation-capable fixtures on a live database')
    schema = 'audit_test_' + uuid.uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('CREATE TABLE {} (id integer PRIMARY KEY)').format(sql.Identifier(schema, 'parent')))
        conn.execute(sql.SQL('CREATE TABLE {} (id integer, parent_id integer REFERENCES {}(id), detail jsonb, happened date)').format(sql.Identifier(schema, 'child'), sql.Identifier(schema, 'parent')))
        conn.execute(sql.SQL('INSERT INTO {} VALUES (1)').format(sql.Identifier(schema, 'parent')))
        conn.execute(sql.SQL("INSERT INTO {} VALUES (1,1,'{{\"a\":[{{\"b\":1}}]}}','2020-01-01'),(2,NULL,NULL,NULL)").format(sql.Identifier(schema, 'child')))
    try:
        yield Reader(dsn, 30000), schema
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        if container:
            container.stop()


def test_read_only_enforcement(audit_database):
    reader, schema = audit_database
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction), reader.connection() as conn:
        conn.execute(sql.SQL('INSERT INTO {} VALUES (2)').format(sql.Identifier(schema, 'parent')))
    with reader.connection() as conn:
        assert conn.execute("SELECT current_setting('transaction_read_only')").fetchone()['current_setting'] == 'on'


def test_catalog_profiles_nested_and_reference_reconciliation(audit_database):
    reader, schema = audit_database
    relations = reader.query('catalog', ([schema],))
    assert {r['source_table'] for r in relations} == {'parent', 'child'}
    columns = reader.query('columns', ([schema],))
    fields = [c for c in columns if c['source_table']=='child']
    profile = reader.table_profile(schema, 'child', fields)
    assert profile['row_count'] == 2
    assert profile['null_2'] == 1
    paths = reader.nested(schema, 'child', 'detail')
    assert [{'kind':'key','value':'a'},{'kind':'array_element'},{'kind':'key','value':'b'}] in [p['path'] for p in paths]
    key = next(k for k in reader.query('keys', ([schema],)) if k['kind']=='f')
    assert reader.references(key)['unresolved_count'] == 0
    assert reader.samples(schema, 'child', ['id']) == [{'id': 1}]
    with pytest.raises(ValueError, match='approved'):
        reader.samples(schema, 'child', ['detail'])
    assert reader.coverage(schema, 'child', ['parent_id']) == [{'parent_id': 1, 'row_count': 1}, {'parent_id': None, 'row_count': 1}]


def test_query_failure_does_not_poison_later_measurements(audit_database):
    reader, schema = audit_database
    with pytest.raises(psycopg.errors.UndefinedTable):
        reader.profile(schema, 'missing', 'id')
    assert reader.profile(schema, 'parent', 'id')['row_count'] == 1


def test_quoted_identifiers_do_not_execute_injection(audit_database):
    reader, schema = audit_database
    with pytest.raises(psycopg.errors.UndefinedTable):
        reader.profile(schema, 'parent; DROP SCHEMA public CASCADE', 'id')
    assert reader.profile(schema, 'parent', 'id')['row_count'] == 1


def test_exported_snapshot_stays_consistent_and_recovers_after_failed_query(audit_database):
    reader,schema=audit_database
    with reader.snapshot():
        assert reader.profile(schema,'parent','id')['row_count']==1
        with psycopg.connect(reader.dsn) as writer:
            writer.execute(sql.SQL('INSERT INTO {} VALUES (9)').format(sql.Identifier(schema,'parent')))
        with pytest.raises(psycopg.errors.UndefinedTable):
            reader.profile(schema,'missing','id')
        assert reader.profile(schema,'parent','id')['row_count']==1
    try:
        assert reader.profile(schema,'parent','id')['row_count']==2
    finally:
        with psycopg.connect(reader.dsn) as writer:
            writer.execute(sql.SQL('DELETE FROM {} WHERE id=9').format(sql.Identifier(schema,'parent')))


def test_actual_identity_queries_and_full_audit_privacy_guard(audit_database):
    reader,schema=audit_database
    tables=('opencivicdata_personidentifier','opencivicdata_person','auth_user')
    with psycopg.connect(reader.dsn) as conn:
        conn.execute(sql.SQL('CREATE TABLE {} (id text PRIMARY KEY,name text)').format(sql.Identifier(schema,tables[1])))
        conn.execute(sql.SQL('CREATE TABLE {} (person_id text,scheme text,identifier text)').format(sql.Identifier(schema,tables[0])))
        conn.execute(sql.SQL('CREATE TABLE {} (id integer,password text)').format(sql.Identifier(schema,tables[2])))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('a','same'),('b','same'),('c','third'),('d','fourth')").format(sql.Identifier(schema,tables[1])))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('a','bioguide','A1'),('a','bioguide','A1'),('b','bioguide','A1'),('d','legacy','')").format(sql.Identifier(schema,tables[0])))
        conn.execute(sql.SQL("INSERT INTO {} VALUES (1,'PRIVATE_ACCOUNT_SENTINEL')").format(sql.Identifier(schema,tables[2])))
    try:
        assert reader.identity_counts(schema)==[{'person_count':4,'missing_bioguide_count':2,'duplicate_bioguide_count':1,'name_collision_groups':1}]
        guide=next(row for row in reader.namespaces(schema) if row['namespace']=='bioguide')
        assert guide=={'namespace':'bioguide','identifier_count':3,'person_count':2,'missing_count':0,'duplicate_assertions':1}
        sampled=[]
        original=reader.samples
        reader.samples=lambda s,t,c: (sampled.append(t),original(s,t,c))[1]
        report=audit(reader,Reader(reader.dsn,5000),[schema])
        assert 'auth_user' not in sampled
        assert 'PRIVATE_ACCOUNT_SENTINEL' not in canonical(report)
        assert report['identity']['cross_provider_links_created']==0
    finally:
        reader.samples=original
        with psycopg.connect(reader.dsn) as conn:
            for table in tables:
                conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema,table)))


def test_tagged_literal_array_key_and_precision_aware_dates(audit_database):
    reader,schema=audit_database
    with psycopg.connect(reader.dsn) as conn:
        conn.execute(sql.SQL('CREATE TABLE {} (detail jsonb,start_date text)').format(sql.Identifier(schema,'tagged_dates')))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('{{\"[]\":1}}','2020'),('[1]','2020-02'),(NULL,'2020-02-29'),(NULL,'2020-02-30')").format(sql.Identifier(schema,'tagged_dates')))
    try:
        paths=reader.nested(schema,'tagged_dates','detail')
        assert [{'kind':'key','value':'[]'}] in [p['path'] for p in paths]
        assert [{'kind':'array_element'}] in [p['path'] for p in paths]
        dates=reader.text_dates(schema,'tagged_dates','start_date')
        assert {row['precision']:row['row_count'] for row in dates}=={'year':1,'month':1,'day':1,'invalid_or_unsupported':1}
        assert next(row['minimum'] for row in dates if row['precision']=='year')=='2020'
    finally:
        with psycopg.connect(reader.dsn) as conn:
            conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema,'tagged_dates')))


def test_parent_derived_coverage_keeps_unresolved_links(audit_database):
    reader, schema = audit_database
    with psycopg.connect(reader.dsn) as conn:
        conn.execute(sql.SQL('CREATE TABLE {} (id text PRIMARY KEY, jurisdiction_id text)').format(sql.Identifier(schema, 'session')))
        conn.execute(sql.SQL('CREATE TABLE {} (id text PRIMARY KEY, legislative_session_id text REFERENCES {} (id))').format(sql.Identifier(schema, 'bill'), sql.Identifier(schema, 'session')))
        conn.execute(sql.SQL('CREATE TABLE {} (id integer PRIMARY KEY, bill_id text REFERENCES {} (id))').format(sql.Identifier(schema, 'action'), sql.Identifier(schema, 'bill')))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('s1','j1')").format(sql.Identifier(schema, 'session')))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('b1','s1')").format(sql.Identifier(schema, 'bill')))
        conn.execute(sql.SQL("INSERT INTO {} VALUES (1,'b1'),(2,NULL)").format(sql.Identifier(schema, 'action')))
    try:
        rows = reader.derived_coverage(
            schema,
            'action',
            [
                {'column': 'bill_id', 'target_schema': schema, 'target_table': 'bill', 'target_column': 'id'},
                {'column': 'legislative_session_id', 'target_schema': schema, 'target_table': 'session', 'target_column': 'id'},
            ],
            [
                {'alias_index': 1, 'column': 'legislative_session_id', 'name': 'legislative_session_id'},
                {'alias_index': 2, 'column': 'jurisdiction_id', 'name': 'jurisdiction_id'},
            ],
        )
        assert sum(row['row_count'] for row in rows) == 2
        missing = next(row for row in rows if row['legislative_session_id'] is None)
        assert missing['row_count'] == 1
        assert missing['unresolved_link_count'] == 1
        assert missing['unresolved_jurisdiction_id_count'] == 1
        linked = next(row for row in rows if row['legislative_session_id'] == 's1')
        assert linked['jurisdiction_id'] == 'j1'
        assert linked['unresolved_link_count'] == 0
    finally:
        with psycopg.connect(reader.dsn) as conn:
            conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema, 'action')))
            conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema, 'bill')))
            conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema, 'session')))


def test_effective_rls_refuses_filtered_counts(audit_database):
    reader,schema=audit_database
    role='audit_filter_'+uuid.uuid4().hex
    with psycopg.connect(reader.dsn) as conn:
        conn.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
        conn.execute(sql.SQL('CREATE TABLE {} (id integer)').format(sql.Identifier(schema,'filtered')))
        conn.execute(sql.SQL('INSERT INTO {} VALUES (1),(2)').format(sql.Identifier(schema,'filtered')))
        conn.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(schema,'filtered')))
        conn.execute(sql.SQL('CREATE POLICY only_one ON {} USING (id=1)').format(sql.Identifier(schema,'filtered')))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
        conn.execute(sql.SQL('GRANT SELECT ON {} TO {}').format(sql.Identifier(schema,'filtered'),sql.Identifier(role)))
    try:
        actor=Reader(psycopg.conninfo.make_conninfo(reader.dsn,options=f'-c role={role}'),5000)
        with pytest.raises(RowFilteringError):
            actor.profile(schema,'filtered','id')
        assert reader.profile(schema,'filtered','id')['row_count']==2
    finally:
        with psycopg.connect(reader.dsn) as conn:
            conn.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier(schema,'filtered')))
            conn.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
