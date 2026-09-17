# OpenStates provider database inventory

Database `openstates` on the same PostgreSQL 17 cluster. This is a
read-only provider snapshot (Django + Open Civic Data). Do not write
warehouse rows into it. Researchers query `core`/`fact`; ingest may
read `openstates_source` FDW.

| Table | Est. rows | Total size |
|---|---:|---|
| `account_emailaddress` | -1 | 32 kB |
| `account_emailconfirmation` | -1 | 32 kB |
| `auth_group` | -1 | 24 kB |
| `auth_group_permissions` | -1 | 32 kB |
| `auth_permission` | -1 | 8192 bytes |
| `auth_user` | -1 | 24 kB |
| `auth_user_groups` | -1 | 32 kB |
| `auth_user_user_permissions` | -1 | 32 kB |
| `boundaries_boundary` | -1 | 96 kB |
| `boundaries_boundaryset` | -1 | 40 kB |
| `bulk_dataexport` | -1 | 24 kB |
| `bundles_bundle` | -1 | 24 kB |
| `bundles_bundlebill` | -1 | 40 kB |
| `dashboards_dataqualityreport` | -1 | 16 kB |
| `dataquality_dataqualityissue` | -1 | 40 kB |
| `dataquality_issueresolverpatch` | -1 | 40 kB |
| `django_admin_log` | -1 | 32 kB |
| `django_content_type` | 127 | 40 kB |
| `django_migrations` | 103 | 32 kB |
| `django_session` | -1 | 32 kB |
| `django_site` | -1 | 56 kB |
| `opencivicdata_bill` | 1564914 | 1262 MB |
| `opencivicdata_billabstract` | 582321 | 408 MB |
| `opencivicdata_billaction` | 13308160 | 4312 MB |
| `opencivicdata_billactionrelatedentity` | 753295 | 153 MB |
| `opencivicdata_billdocument` | 938835 | 233 MB |
| `opencivicdata_billdocumentlink` | 1011207 | 229 MB |
| `opencivicdata_billidentifier` | 232256 | 75 MB |
| `opencivicdata_billsource` | 2416757 | 776 MB |
| `opencivicdata_billsponsorship` | 7379103 | 2032 MB |
| `opencivicdata_billtitle` | 155952 | 62 MB |
| `opencivicdata_billversion` | 2785923 | 729 MB |
| `opencivicdata_billversionlink` | 3624397 | 817 MB |
| `opencivicdata_division` | 193807 | 98 MB |
| `opencivicdata_event` | 191730 | 171 MB |
| `opencivicdata_eventagendaitem` | 555360 | 175 MB |
| `opencivicdata_eventagendamedia` | -1 | 80 kB |
| `opencivicdata_eventdocument` | 459663 | 168 MB |
| `opencivicdata_eventlocation` | 7520 | 2040 kB |
| `opencivicdata_eventmedia` | 48968 | 24 MB |
| `opencivicdata_eventparticipant` | 858894 | 213 MB |
| `opencivicdata_eventrelatedentity` | 764523 | 236 MB |
| `opencivicdata_jurisdiction` | 1857 | 1032 kB |
| `opencivicdata_legislativesession` | 1082 | 352 kB |
| `opencivicdata_membership` | 91751 | 68 MB |
| `opencivicdata_organization` | 5005 | 7048 kB |
| `opencivicdata_person` | 22702 | 16 MB |
| `opencivicdata_personidentifier` | 35017 | 8776 kB |
| `opencivicdata_personlink` | 42493 | 13 MB |
| `opencivicdata_personname` | 35750 | 11 MB |
| `opencivicdata_personsource` | 91585 | 23 MB |
| `opencivicdata_personvote` | 52349852 | 12 GB |
| `opencivicdata_post` | 7657 | 5680 kB |
| `opencivicdata_relatedbill` | 380023 | 151 MB |
| `opencivicdata_searchablebill` | 1542556 | 11 GB |
| `opencivicdata_votecount` | 3895098 | 799 MB |
| `opencivicdata_voteevent` | 1194349 | 924 MB |
| `opencivicdata_votesource` | 1243492 | 461 MB |
| `openstates_personoffice` | 15505 | 5344 kB |
| `people_admin_deltaset` | -1 | 16 kB |
| `people_admin_newperson` | -1 | 24 kB |
| `people_admin_persondelta` | -1 | 40 kB |
| `people_admin_personretirement` | -1 | 40 kB |
| `people_admin_unmatchedname` | -1 | 32 kB |
| `profiles_notification` | -1 | 16 kB |
| `profiles_profile` | -1 | 48 kB |
| `profiles_subscription` | -1 | 56 kB |
| `profiles_usagereport` | -1 | 24 kB |
| `pupa_importobjects` | -1 | 16 kB |
| `pupa_runplan` | -1 | 32 kB |
| `pupa_scrapeobjects` | -1 | 16 kB |
| `pupa_scrapereport` | -1 | 24 kB |
| `pupa_sessiondataqualityreport` | -1 | 24 kB |
| `simplekeys_key` | -1 | 56 kB |
| `simplekeys_limit` | -1 | 32 kB |
| `simplekeys_tier` | -1 | 24 kB |
| `simplekeys_zone` | -1 | 24 kB |
| `socialaccount_socialaccount` | -1 | 32 kB |
| `socialaccount_socialapp` | -1 | 16 kB |
| `socialaccount_socialapp_sites` | -1 | 32 kB |
| `socialaccount_socialtoken` | -1 | 40 kB |
| `spatial_ref_sys` | 8500 | 7144 kB |
| `v1_legacybillmapping` | -1 | 32 kB |
| `widgets_widgetconfig` | -1 | 24 kB |

## `opencivicdata_*` columns

### `public.opencivicdata_bill`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(45)` | NO |
| `identifier` | `character varying(100)` | NO |
| `title` | `text` | NO |
| `classification` | `text[]` | NO |
| `subject` | `text[]` | NO |
| `from_organization_id` | `character varying(53)` | YES |
| `legislative_session_id` | `uuid` | NO |
| `first_action_date` | `character varying(25)` | YES |
| `latest_action_date` | `character varying(25)` | YES |
| `latest_action_description` | `text` | NO |
| `latest_passage_date` | `character varying(25)` | YES |
| `citations` | `jsonb` | NO |

### `public.opencivicdata_billabstract`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `abstract` | `text` | NO |
| `note` | `text` | NO |
| `bill_id` | `character varying(45)` | NO |

### `public.opencivicdata_billaction`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `description` | `text` | NO |
| `date` | `character varying(25)` | NO |
| `classification` | `text[]` | NO |
| `order` | `integer` | NO |
| `bill_id` | `character varying(45)` | NO |
| `organization_id` | `character varying(53)` | NO |

### `public.opencivicdata_billactionrelatedentity`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(2000)` | NO |
| `entity_type` | `character varying(20)` | NO |
| `action_id` | `uuid` | NO |
| `organization_id` | `character varying(53)` | YES |
| `person_id` | `character varying(47)` | YES |

### `public.opencivicdata_billdocument`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `date` | `character varying(10)` | NO |
| `bill_id` | `character varying(45)` | NO |
| `extras` | `jsonb` | NO |
| `classification` | `character varying(100)` | NO |

### `public.opencivicdata_billdocumentlink`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `media_type` | `character varying(100)` | NO |
| `url` | `character varying(2000)` | NO |
| `document_id` | `uuid` | NO |

### `public.opencivicdata_billidentifier`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `identifier` | `character varying(300)` | NO |
| `bill_id` | `character varying(45)` | NO |

### `public.opencivicdata_billsource`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `url` | `character varying(2000)` | NO |
| `bill_id` | `character varying(45)` | NO |

### `public.opencivicdata_billsponsorship`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(2000)` | NO |
| `entity_type` | `character varying(20)` | NO |
| `primary` | `boolean` | NO |
| `classification` | `character varying(100)` | NO |
| `bill_id` | `character varying(45)` | NO |
| `organization_id` | `character varying(53)` | YES |
| `person_id` | `character varying(47)` | YES |

### `public.opencivicdata_billtitle`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `title` | `text` | NO |
| `note` | `text` | NO |
| `bill_id` | `character varying(45)` | NO |

### `public.opencivicdata_billversion`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `date` | `character varying(10)` | NO |
| `bill_id` | `character varying(45)` | NO |
| `extras` | `jsonb` | NO |
| `classification` | `character varying(100)` | NO |

### `public.opencivicdata_billversionlink`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `media_type` | `character varying(100)` | NO |
| `url` | `character varying(2000)` | NO |
| `version_id` | `uuid` | NO |

### `public.opencivicdata_division`

| Column | Type | Null |
|---|---|---|
| `id` | `character varying(300)` | NO |
| `name` | `character varying(300)` | NO |
| `country` | `character varying(2)` | NO |
| `subtype1` | `character varying(50)` | NO |
| `subid1` | `character varying(100)` | NO |
| `subtype2` | `character varying(50)` | NO |
| `subid2` | `character varying(100)` | NO |
| `subtype3` | `character varying(50)` | NO |
| `subid3` | `character varying(100)` | NO |
| `subtype4` | `character varying(50)` | NO |
| `subid4` | `character varying(100)` | NO |
| `subtype5` | `character varying(50)` | NO |
| `subid5` | `character varying(100)` | NO |
| `subtype6` | `character varying(50)` | NO |
| `subid6` | `character varying(100)` | NO |
| `subtype7` | `character varying(50)` | NO |
| `subid7` | `character varying(100)` | NO |
| `redirect_id` | `character varying(300)` | YES |

### `public.opencivicdata_event`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(46)` | NO |
| `name` | `character varying(1000)` | NO |
| `description` | `text` | NO |
| `classification` | `character varying(100)` | NO |
| `start_date` | `character varying(25)` | NO |
| `end_date` | `character varying(25)` | NO |
| `all_day` | `boolean` | NO |
| `status` | `character varying(20)` | NO |
| `jurisdiction_id` | `character varying(300)` | NO |
| `location_id` | `uuid` | YES |
| `dedupe_key` | `character varying(500)` | YES |
| `deleted` | `boolean` | NO |
| `upstream_id` | `character varying(300)` | NO |
| `links` | `jsonb` | NO |
| `sources` | `jsonb` | NO |

### `public.opencivicdata_eventagendaitem`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `description` | `text` | NO |
| `classification` | `text[]` | NO |
| `order` | `integer` | NO |
| `subjects` | `text[]` | NO |
| `notes` | `text[]` | NO |
| `event_id` | `character varying(46)` | NO |
| `extras` | `jsonb` | NO |

### `public.opencivicdata_eventagendamedia`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `date` | `character varying(25)` | NO |
| `offset` | `integer` | YES |
| `agenda_item_id` | `uuid` | NO |
| `classification` | `character varying(100)` | NO |
| `links` | `jsonb` | NO |

### `public.opencivicdata_eventdocument`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `text` | NO |
| `date` | `character varying(25)` | NO |
| `event_id` | `character varying(46)` | NO |
| `classification` | `character varying(50)` | NO |
| `links` | `jsonb` | NO |

### `public.opencivicdata_eventlocation`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(200)` | NO |
| `url` | `character varying(2000)` | NO |
| `coordinates` | `geometry(Point,4326)` | YES |
| `jurisdiction_id` | `character varying(300)` | NO |

### `public.opencivicdata_eventmedia`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `date` | `character varying(25)` | NO |
| `offset` | `integer` | YES |
| `event_id` | `character varying(46)` | NO |
| `classification` | `character varying(50)` | NO |
| `links` | `jsonb` | NO |

### `public.opencivicdata_eventparticipant`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(2000)` | NO |
| `entity_type` | `character varying(20)` | NO |
| `note` | `text` | NO |
| `event_id` | `character varying(46)` | NO |
| `organization_id` | `character varying(53)` | YES |
| `person_id` | `character varying(47)` | YES |

### `public.opencivicdata_eventrelatedentity`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(2000)` | NO |
| `entity_type` | `character varying(20)` | NO |
| `note` | `text` | NO |
| `agenda_item_id` | `uuid` | NO |
| `bill_id` | `character varying(45)` | YES |
| `organization_id` | `character varying(53)` | YES |
| `person_id` | `character varying(47)` | YES |
| `vote_event_id` | `character varying(45)` | YES |

### `public.opencivicdata_jurisdiction`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(300)` | NO |
| `name` | `character varying(300)` | NO |
| `url` | `character varying(2000)` | NO |
| `classification` | `character varying(50)` | NO |
| `division_id` | `character varying(300)` | YES |
| `latest_bill_update` | `timestamp with time zone` | NO |
| `latest_people_update` | `timestamp with time zone` | NO |

### `public.opencivicdata_legislativesession`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `identifier` | `character varying(100)` | NO |
| `name` | `character varying(300)` | NO |
| `classification` | `character varying(100)` | NO |
| `start_date` | `character varying(10)` | NO |
| `end_date` | `character varying(10)` | NO |
| `jurisdiction_id` | `character varying(300)` | NO |
| `active` | `boolean` | NO |

### `public.opencivicdata_membership`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(51)` | NO |
| `person_name` | `character varying(300)` | NO |
| `role` | `character varying(300)` | NO |
| `start_date` | `character varying(10)` | NO |
| `end_date` | `character varying(10)` | NO |
| `organization_id` | `character varying(53)` | NO |
| `person_id` | `character varying(47)` | YES |
| `post_id` | `character varying(45)` | YES |

### `public.opencivicdata_organization`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(53)` | NO |
| `name` | `character varying(300)` | NO |
| `classification` | `character varying(100)` | NO |
| `jurisdiction_id` | `character varying(300)` | YES |
| `parent_id` | `character varying(53)` | YES |
| `links` | `jsonb` | NO |
| `sources` | `jsonb` | NO |
| `other_names` | `jsonb` | NO |

### `public.opencivicdata_person`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(47)` | NO |
| `name` | `character varying(300)` | NO |
| `family_name` | `character varying(100)` | NO |
| `given_name` | `character varying(100)` | NO |
| `image` | `character varying(2000)` | NO |
| `gender` | `character varying(100)` | NO |
| `biography` | `text` | NO |
| `birth_date` | `character varying(10)` | NO |
| `death_date` | `character varying(10)` | NO |
| `primary_party` | `character varying(100)` | NO |
| `current_jurisdiction_id` | `character varying(300)` | YES |
| `current_role` | `jsonb` | YES |
| `email` | `character varying(300)` | NO |

### `public.opencivicdata_personidentifier`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `identifier` | `character varying(300)` | NO |
| `scheme` | `character varying(300)` | NO |
| `person_id` | `character varying(47)` | NO |

### `public.opencivicdata_personlink`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `url` | `character varying(2000)` | NO |
| `person_id` | `character varying(47)` | NO |

### `public.opencivicdata_personname`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `name` | `character varying(500)` | NO |
| `note` | `character varying(500)` | NO |
| `start_date` | `character varying(10)` | NO |
| `end_date` | `character varying(10)` | NO |
| `person_id` | `character varying(47)` | NO |

### `public.opencivicdata_personsource`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `url` | `character varying(2000)` | NO |
| `person_id` | `character varying(47)` | NO |

### `public.opencivicdata_personvote`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `option` | `character varying(50)` | NO |
| `voter_name` | `character varying(300)` | NO |
| `note` | `text` | NO |
| `vote_event_id` | `character varying(45)` | NO |
| `voter_id` | `character varying(47)` | YES |

### `public.opencivicdata_post`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(45)` | NO |
| `label` | `character varying(300)` | NO |
| `role` | `character varying(300)` | NO |
| `division_id` | `character varying(300)` | YES |
| `organization_id` | `character varying(53)` | NO |
| `maximum_memberships` | `integer` | NO |

### `public.opencivicdata_relatedbill`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `identifier` | `character varying(100)` | NO |
| `legislative_session` | `character varying(100)` | NO |
| `relation_type` | `character varying(100)` | NO |
| `bill_id` | `character varying(45)` | NO |
| `related_bill_id` | `character varying(45)` | YES |

### `public.opencivicdata_searchablebill`

| Column | Type | Null |
|---|---|---|
| `id` | `integer` | NO |
| `search_vector` | `tsvector` | NO |
| `all_titles` | `text` | NO |
| `raw_text` | `text` | NO |
| `is_error` | `boolean` | NO |
| `created_at` | `timestamp with time zone` | NO |
| `bill_id` | `character varying(45)` | YES |
| `version_link_id` | `uuid` | YES |

### `public.opencivicdata_votecount`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `option` | `character varying(50)` | NO |
| `value` | `integer` | NO |
| `vote_event_id` | `character varying(45)` | NO |

### `public.opencivicdata_voteevent`

| Column | Type | Null |
|---|---|---|
| `created_at` | `timestamp with time zone` | NO |
| `updated_at` | `timestamp with time zone` | NO |
| `extras` | `jsonb` | NO |
| `id` | `character varying(45)` | NO |
| `identifier` | `character varying(300)` | NO |
| `motion_text` | `text` | NO |
| `motion_classification` | `text[]` | NO |
| `start_date` | `character varying(25)` | NO |
| `result` | `character varying(50)` | NO |
| `bill_id` | `character varying(45)` | YES |
| `bill_action_id` | `uuid` | YES |
| `legislative_session_id` | `uuid` | NO |
| `organization_id` | `character varying(53)` | NO |
| `order` | `integer` | NO |
| `dedupe_key` | `character varying(500)` | YES |

### `public.opencivicdata_votesource`

| Column | Type | Null |
|---|---|---|
| `id` | `uuid` | NO |
| `note` | `character varying(300)` | NO |
| `url` | `character varying(2000)` | NO |
| `vote_event_id` | `character varying(45)` | NO |
