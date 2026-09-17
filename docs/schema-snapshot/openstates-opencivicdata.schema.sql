--
-- PostgreSQL database dump
--

\restrict opendiscourseschemasnapshot

-- Dumped from database version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)
-- Dumped by pg_dump version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_table_access_method = heap;

--
-- Name: opencivicdata_bill; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_bill (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(45) NOT NULL,
    identifier character varying(100) NOT NULL,
    title text NOT NULL,
    classification text[] NOT NULL,
    subject text[] NOT NULL,
    from_organization_id character varying(53),
    legislative_session_id uuid NOT NULL,
    first_action_date character varying(25),
    latest_action_date character varying(25),
    latest_action_description text NOT NULL,
    latest_passage_date character varying(25),
    citations jsonb NOT NULL
);


ALTER TABLE public.opencivicdata_bill OWNER TO postgres;

--
-- Name: opencivicdata_billabstract; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billabstract (
    id uuid NOT NULL,
    abstract text NOT NULL,
    note text NOT NULL,
    bill_id character varying(45) NOT NULL
);


ALTER TABLE public.opencivicdata_billabstract OWNER TO postgres;

--
-- Name: opencivicdata_billaction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billaction (
    id uuid NOT NULL,
    description text NOT NULL,
    date character varying(25) NOT NULL,
    classification text[] NOT NULL,
    "order" integer NOT NULL,
    bill_id character varying(45) NOT NULL,
    organization_id character varying(53) NOT NULL,
    CONSTRAINT opencivicdata_billaction_order_check CHECK (("order" >= 0))
);


ALTER TABLE public.opencivicdata_billaction OWNER TO postgres;

--
-- Name: opencivicdata_billactionrelatedentity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billactionrelatedentity (
    id uuid NOT NULL,
    name character varying(2000) NOT NULL,
    entity_type character varying(20) NOT NULL,
    action_id uuid NOT NULL,
    organization_id character varying(53),
    person_id character varying(47)
);


ALTER TABLE public.opencivicdata_billactionrelatedentity OWNER TO postgres;

--
-- Name: opencivicdata_billdocument; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billdocument (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    date character varying(10) NOT NULL,
    bill_id character varying(45) NOT NULL,
    extras jsonb NOT NULL,
    classification character varying(100) NOT NULL
);


ALTER TABLE public.opencivicdata_billdocument OWNER TO postgres;

--
-- Name: opencivicdata_billdocumentlink; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billdocumentlink (
    id uuid NOT NULL,
    media_type character varying(100) NOT NULL,
    url character varying(2000) NOT NULL,
    document_id uuid NOT NULL
);


ALTER TABLE public.opencivicdata_billdocumentlink OWNER TO postgres;

--
-- Name: opencivicdata_billidentifier; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billidentifier (
    id uuid NOT NULL,
    identifier character varying(300) NOT NULL,
    bill_id character varying(45) NOT NULL
);


ALTER TABLE public.opencivicdata_billidentifier OWNER TO postgres;

--
-- Name: opencivicdata_billsource; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billsource (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    bill_id character varying(45) NOT NULL
);


ALTER TABLE public.opencivicdata_billsource OWNER TO postgres;

--
-- Name: opencivicdata_billsponsorship; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billsponsorship (
    id uuid NOT NULL,
    name character varying(2000) NOT NULL,
    entity_type character varying(20) NOT NULL,
    "primary" boolean NOT NULL,
    classification character varying(100) NOT NULL,
    bill_id character varying(45) NOT NULL,
    organization_id character varying(53),
    person_id character varying(47)
);


ALTER TABLE public.opencivicdata_billsponsorship OWNER TO postgres;

--
-- Name: opencivicdata_billtitle; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billtitle (
    id uuid NOT NULL,
    title text NOT NULL,
    note text NOT NULL,
    bill_id character varying(45) NOT NULL
);


ALTER TABLE public.opencivicdata_billtitle OWNER TO postgres;

--
-- Name: opencivicdata_billversion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billversion (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    date character varying(10) NOT NULL,
    bill_id character varying(45) NOT NULL,
    extras jsonb NOT NULL,
    classification character varying(100) NOT NULL
);


ALTER TABLE public.opencivicdata_billversion OWNER TO postgres;

--
-- Name: opencivicdata_billversionlink; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_billversionlink (
    id uuid NOT NULL,
    media_type character varying(100) NOT NULL,
    url character varying(2000) NOT NULL,
    version_id uuid NOT NULL
);


ALTER TABLE public.opencivicdata_billversionlink OWNER TO postgres;

--
-- Name: opencivicdata_division; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_division (
    id character varying(300) NOT NULL,
    name character varying(300) NOT NULL,
    country character varying(2) NOT NULL,
    subtype1 character varying(50) NOT NULL,
    subid1 character varying(100) NOT NULL,
    subtype2 character varying(50) NOT NULL,
    subid2 character varying(100) NOT NULL,
    subtype3 character varying(50) NOT NULL,
    subid3 character varying(100) NOT NULL,
    subtype4 character varying(50) NOT NULL,
    subid4 character varying(100) NOT NULL,
    subtype5 character varying(50) NOT NULL,
    subid5 character varying(100) NOT NULL,
    subtype6 character varying(50) NOT NULL,
    subid6 character varying(100) NOT NULL,
    subtype7 character varying(50) NOT NULL,
    subid7 character varying(100) NOT NULL,
    redirect_id character varying(300)
);


ALTER TABLE public.opencivicdata_division OWNER TO postgres;

--
-- Name: opencivicdata_event; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_event (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(46) NOT NULL,
    name character varying(1000) NOT NULL,
    description text NOT NULL,
    classification character varying(100) NOT NULL,
    start_date character varying(25) NOT NULL,
    end_date character varying(25) NOT NULL,
    all_day boolean NOT NULL,
    status character varying(20) NOT NULL,
    jurisdiction_id character varying(300) NOT NULL,
    location_id uuid,
    dedupe_key character varying(500),
    deleted boolean NOT NULL,
    upstream_id character varying(300) NOT NULL,
    links jsonb NOT NULL,
    sources jsonb NOT NULL
);


ALTER TABLE public.opencivicdata_event OWNER TO postgres;

--
-- Name: opencivicdata_eventagendaitem; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventagendaitem (
    id uuid NOT NULL,
    description text NOT NULL,
    classification text[] NOT NULL,
    "order" integer NOT NULL,
    subjects text[] NOT NULL,
    notes text[] NOT NULL,
    event_id character varying(46) NOT NULL,
    extras jsonb NOT NULL,
    CONSTRAINT opencivicdata_eventagendaitem_order_ac22bf4b_check CHECK (("order" >= 0))
);


ALTER TABLE public.opencivicdata_eventagendaitem OWNER TO postgres;

--
-- Name: opencivicdata_eventagendamedia; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventagendamedia (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    date character varying(25) NOT NULL,
    "offset" integer,
    agenda_item_id uuid NOT NULL,
    classification character varying(100) NOT NULL,
    links jsonb NOT NULL,
    CONSTRAINT opencivicdata_eventagendamedia_offset_check CHECK (("offset" >= 0))
);


ALTER TABLE public.opencivicdata_eventagendamedia OWNER TO postgres;

--
-- Name: opencivicdata_eventdocument; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventdocument (
    id uuid NOT NULL,
    note text NOT NULL,
    date character varying(25) NOT NULL,
    event_id character varying(46) NOT NULL,
    classification character varying(50) NOT NULL,
    links jsonb NOT NULL
);


ALTER TABLE public.opencivicdata_eventdocument OWNER TO postgres;

--
-- Name: opencivicdata_eventlocation; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventlocation (
    id uuid NOT NULL,
    name character varying(200) NOT NULL,
    url character varying(2000) NOT NULL,
    coordinates public.geometry(Point,4326),
    jurisdiction_id character varying(300) NOT NULL
);


ALTER TABLE public.opencivicdata_eventlocation OWNER TO postgres;

--
-- Name: opencivicdata_eventmedia; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventmedia (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    date character varying(25) NOT NULL,
    "offset" integer,
    event_id character varying(46) NOT NULL,
    classification character varying(50) NOT NULL,
    links jsonb NOT NULL,
    CONSTRAINT opencivicdata_eventmedia_offset_check CHECK (("offset" >= 0))
);


ALTER TABLE public.opencivicdata_eventmedia OWNER TO postgres;

--
-- Name: opencivicdata_eventparticipant; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventparticipant (
    id uuid NOT NULL,
    name character varying(2000) NOT NULL,
    entity_type character varying(20) NOT NULL,
    note text NOT NULL,
    event_id character varying(46) NOT NULL,
    organization_id character varying(53),
    person_id character varying(47)
);


ALTER TABLE public.opencivicdata_eventparticipant OWNER TO postgres;

--
-- Name: opencivicdata_eventrelatedentity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_eventrelatedentity (
    id uuid NOT NULL,
    name character varying(2000) NOT NULL,
    entity_type character varying(20) NOT NULL,
    note text NOT NULL,
    agenda_item_id uuid NOT NULL,
    bill_id character varying(45),
    organization_id character varying(53),
    person_id character varying(47),
    vote_event_id character varying(45)
);


ALTER TABLE public.opencivicdata_eventrelatedentity OWNER TO postgres;

--
-- Name: opencivicdata_jurisdiction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_jurisdiction (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(300) NOT NULL,
    name character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    classification character varying(50) NOT NULL,
    division_id character varying(300),
    latest_bill_update timestamp with time zone NOT NULL,
    latest_people_update timestamp with time zone NOT NULL
);


ALTER TABLE public.opencivicdata_jurisdiction OWNER TO postgres;

--
-- Name: opencivicdata_legislativesession; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_legislativesession (
    id uuid NOT NULL,
    identifier character varying(100) NOT NULL,
    name character varying(300) NOT NULL,
    classification character varying(100) NOT NULL,
    start_date character varying(10) NOT NULL,
    end_date character varying(10) NOT NULL,
    jurisdiction_id character varying(300) NOT NULL,
    active boolean NOT NULL
);


ALTER TABLE public.opencivicdata_legislativesession OWNER TO postgres;

--
-- Name: opencivicdata_membership; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_membership (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(51) NOT NULL,
    person_name character varying(300) NOT NULL,
    role character varying(300) NOT NULL,
    start_date character varying(10) NOT NULL,
    end_date character varying(10) NOT NULL,
    organization_id character varying(53) NOT NULL,
    person_id character varying(47),
    post_id character varying(45)
);


ALTER TABLE public.opencivicdata_membership OWNER TO postgres;

--
-- Name: opencivicdata_organization; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_organization (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(53) NOT NULL,
    name character varying(300) NOT NULL,
    classification character varying(100) NOT NULL,
    jurisdiction_id character varying(300),
    parent_id character varying(53),
    links jsonb NOT NULL,
    sources jsonb NOT NULL,
    other_names jsonb NOT NULL
);


ALTER TABLE public.opencivicdata_organization OWNER TO postgres;

--
-- Name: opencivicdata_person; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_person (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(47) NOT NULL,
    name character varying(300) NOT NULL,
    family_name character varying(100) NOT NULL,
    given_name character varying(100) NOT NULL,
    image character varying(2000) NOT NULL,
    gender character varying(100) NOT NULL,
    biography text NOT NULL,
    birth_date character varying(10) NOT NULL,
    death_date character varying(10) NOT NULL,
    primary_party character varying(100) NOT NULL,
    current_jurisdiction_id character varying(300),
    "current_role" jsonb,
    email character varying(300) NOT NULL
);


ALTER TABLE public.opencivicdata_person OWNER TO postgres;

--
-- Name: opencivicdata_personidentifier; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_personidentifier (
    id uuid NOT NULL,
    identifier character varying(300) NOT NULL,
    scheme character varying(300) NOT NULL,
    person_id character varying(47) NOT NULL
);


ALTER TABLE public.opencivicdata_personidentifier OWNER TO postgres;

--
-- Name: opencivicdata_personlink; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_personlink (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    person_id character varying(47) NOT NULL
);


ALTER TABLE public.opencivicdata_personlink OWNER TO postgres;

--
-- Name: opencivicdata_personname; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_personname (
    id uuid NOT NULL,
    name character varying(500) NOT NULL,
    note character varying(500) NOT NULL,
    start_date character varying(10) NOT NULL,
    end_date character varying(10) NOT NULL,
    person_id character varying(47) NOT NULL
);


ALTER TABLE public.opencivicdata_personname OWNER TO postgres;

--
-- Name: opencivicdata_personsource; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_personsource (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    person_id character varying(47) NOT NULL
);


ALTER TABLE public.opencivicdata_personsource OWNER TO postgres;

--
-- Name: opencivicdata_personvote; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_personvote (
    id uuid NOT NULL,
    option character varying(50) NOT NULL,
    voter_name character varying(300) NOT NULL,
    note text NOT NULL,
    vote_event_id character varying(45) NOT NULL,
    voter_id character varying(47)
);


ALTER TABLE public.opencivicdata_personvote OWNER TO postgres;

--
-- Name: opencivicdata_post; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_post (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(45) NOT NULL,
    label character varying(300) NOT NULL,
    role character varying(300) NOT NULL,
    division_id character varying(300),
    organization_id character varying(53) NOT NULL,
    maximum_memberships integer NOT NULL,
    CONSTRAINT opencivicdata_post_maximum_memberships_check CHECK ((maximum_memberships >= 0))
);


ALTER TABLE public.opencivicdata_post OWNER TO postgres;

--
-- Name: opencivicdata_relatedbill; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_relatedbill (
    id uuid NOT NULL,
    identifier character varying(100) NOT NULL,
    legislative_session character varying(100) NOT NULL,
    relation_type character varying(100) NOT NULL,
    bill_id character varying(45) NOT NULL,
    related_bill_id character varying(45)
);


ALTER TABLE public.opencivicdata_relatedbill OWNER TO postgres;

--
-- Name: opencivicdata_searchablebill; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_searchablebill (
    id integer NOT NULL,
    search_vector tsvector NOT NULL,
    all_titles text NOT NULL,
    raw_text text NOT NULL,
    is_error boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    bill_id character varying(45),
    version_link_id uuid
);


ALTER TABLE public.opencivicdata_searchablebill OWNER TO postgres;

--
-- Name: opencivicdata_searchablebill_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.opencivicdata_searchablebill_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.opencivicdata_searchablebill_id_seq OWNER TO postgres;

--
-- Name: opencivicdata_searchablebill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.opencivicdata_searchablebill_id_seq OWNED BY public.opencivicdata_searchablebill.id;


--
-- Name: opencivicdata_votecount; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_votecount (
    id uuid NOT NULL,
    option character varying(50) NOT NULL,
    value integer NOT NULL,
    vote_event_id character varying(45) NOT NULL,
    CONSTRAINT opencivicdata_votecount_value_check CHECK ((value >= 0))
);


ALTER TABLE public.opencivicdata_votecount OWNER TO postgres;

--
-- Name: opencivicdata_voteevent; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_voteevent (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(45) NOT NULL,
    identifier character varying(300) NOT NULL,
    motion_text text NOT NULL,
    motion_classification text[] NOT NULL,
    start_date character varying(25) NOT NULL,
    result character varying(50) NOT NULL,
    bill_id character varying(45),
    bill_action_id uuid,
    legislative_session_id uuid NOT NULL,
    organization_id character varying(53) NOT NULL,
    "order" integer NOT NULL,
    dedupe_key character varying(500),
    CONSTRAINT opencivicdata_voteevent_order_check CHECK (("order" >= 0))
);


ALTER TABLE public.opencivicdata_voteevent OWNER TO postgres;

--
-- Name: opencivicdata_votesource; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.opencivicdata_votesource (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    vote_event_id character varying(45) NOT NULL
);


ALTER TABLE public.opencivicdata_votesource OWNER TO postgres;

--
-- Name: opencivicdata_searchablebill id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill ALTER COLUMN id SET DEFAULT nextval('public.opencivicdata_searchablebill_id_seq'::regclass);


--
-- Name: opencivicdata_bill opencivicdata_bill_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_bill
    ADD CONSTRAINT opencivicdata_bill_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billabstract opencivicdata_billabstract_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billabstract
    ADD CONSTRAINT opencivicdata_billabstract_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billaction opencivicdata_billaction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billaction
    ADD CONSTRAINT opencivicdata_billaction_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billactionrelatedentity opencivicdata_billactionrelatedentity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billactionrelatedentity
    ADD CONSTRAINT opencivicdata_billactionrelatedentity_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billdocument opencivicdata_billdocument_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billdocument
    ADD CONSTRAINT opencivicdata_billdocument_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billdocumentlink opencivicdata_billdocumentlink_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billdocumentlink
    ADD CONSTRAINT opencivicdata_billdocumentlink_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billidentifier opencivicdata_billidentifier_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billidentifier
    ADD CONSTRAINT opencivicdata_billidentifier_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billsource opencivicdata_billsource_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsource
    ADD CONSTRAINT opencivicdata_billsource_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billsponsorship opencivicdata_billsponsorship_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsponsorship
    ADD CONSTRAINT opencivicdata_billsponsorship_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billtitle opencivicdata_billtitle_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billtitle
    ADD CONSTRAINT opencivicdata_billtitle_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billversion opencivicdata_billversion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billversion
    ADD CONSTRAINT opencivicdata_billversion_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_billversionlink opencivicdata_billversionlink_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billversionlink
    ADD CONSTRAINT opencivicdata_billversionlink_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_division opencivicdata_division_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_division
    ADD CONSTRAINT opencivicdata_division_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_event opencivicdata_event_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_event
    ADD CONSTRAINT opencivicdata_event_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventagendaitem opencivicdata_eventagendaitem_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventagendaitem
    ADD CONSTRAINT opencivicdata_eventagendaitem_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventagendamedia opencivicdata_eventagendamedia_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventagendamedia
    ADD CONSTRAINT opencivicdata_eventagendamedia_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventdocument opencivicdata_eventdocument_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventdocument
    ADD CONSTRAINT opencivicdata_eventdocument_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventlocation opencivicdata_eventlocation_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventlocation
    ADD CONSTRAINT opencivicdata_eventlocation_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventmedia opencivicdata_eventmedia_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventmedia
    ADD CONSTRAINT opencivicdata_eventmedia_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventparticipant opencivicdata_eventparticipant_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventparticipant
    ADD CONSTRAINT opencivicdata_eventparticipant_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventrelatedentity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventrelatedentity_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_jurisdiction opencivicdata_jurisdiction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_jurisdiction
    ADD CONSTRAINT opencivicdata_jurisdiction_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_legislativesession opencivicdata_legislativesession_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_legislativesession
    ADD CONSTRAINT opencivicdata_legislativesession_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_membership opencivicdata_membership_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_membership
    ADD CONSTRAINT opencivicdata_membership_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_organization opencivicdata_organization_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_organization
    ADD CONSTRAINT opencivicdata_organization_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_person opencivicdata_person_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_person
    ADD CONSTRAINT opencivicdata_person_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_personidentifier opencivicdata_personidentifier_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personidentifier
    ADD CONSTRAINT opencivicdata_personidentifier_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_personlink opencivicdata_personlink_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personlink
    ADD CONSTRAINT opencivicdata_personlink_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_personname opencivicdata_personname_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personname
    ADD CONSTRAINT opencivicdata_personname_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_personsource opencivicdata_personsource_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personsource
    ADD CONSTRAINT opencivicdata_personsource_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_personvote opencivicdata_personvote_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personvote
    ADD CONSTRAINT opencivicdata_personvote_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_post opencivicdata_post_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_post
    ADD CONSTRAINT opencivicdata_post_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_relatedbill opencivicdata_relatedbill_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_relatedbill
    ADD CONSTRAINT opencivicdata_relatedbill_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_searchablebill opencivicdata_searchablebill_bill_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill
    ADD CONSTRAINT opencivicdata_searchablebill_bill_id_key UNIQUE (bill_id);


--
-- Name: opencivicdata_searchablebill opencivicdata_searchablebill_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill
    ADD CONSTRAINT opencivicdata_searchablebill_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_searchablebill opencivicdata_searchablebill_version_link_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill
    ADD CONSTRAINT opencivicdata_searchablebill_version_link_id_key UNIQUE (version_link_id);


--
-- Name: opencivicdata_votecount opencivicdata_votecount_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_votecount
    ADD CONSTRAINT opencivicdata_votecount_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_voteevent opencivicdata_voteevent_bill_action_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteevent_bill_action_id_key UNIQUE (bill_action_id);


--
-- Name: opencivicdata_voteevent opencivicdata_voteevent_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteevent_pkey PRIMARY KEY (id);


--
-- Name: opencivicdata_votesource opencivicdata_votesource_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_votesource
    ADD CONSTRAINT opencivicdata_votesource_pkey PRIMARY KEY (id);


--
-- Name: idx_opencivicdata_personvote_vote_event_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_opencivicdata_personvote_vote_event_id ON public.opencivicdata_personvote USING btree (vote_event_id);


--
-- Name: idx_opencivicdata_voteevent_legislative_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_opencivicdata_voteevent_legislative_session_id ON public.opencivicdata_voteevent USING btree (legislative_session_id);


--
-- Name: opencivicdata_bill_from_organization_id_e96ed21d; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_bill_from_organization_id_e96ed21d ON public.opencivicdata_bill USING btree (from_organization_id);


--
-- Name: opencivicdata_bill_from_organization_id_e96ed21d_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_bill_from_organization_id_e96ed21d_like ON public.opencivicdata_bill USING btree (from_organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_bill_from_organization_id_leg_19e983a6_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_bill_from_organization_id_leg_19e983a6_idx ON public.opencivicdata_bill USING btree (from_organization_id, legislative_session_id, identifier);


--
-- Name: opencivicdata_bill_id_2d3f3e7c_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_bill_id_2d3f3e7c_like ON public.opencivicdata_bill USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_bill_legislative_session_id_ef50ac55; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_bill_legislative_session_id_ef50ac55 ON public.opencivicdata_bill USING btree (legislative_session_id);


--
-- Name: opencivicdata_billabstract_bill_id_ae9ce636; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billabstract_bill_id_ae9ce636 ON public.opencivicdata_billabstract USING btree (bill_id);


--
-- Name: opencivicdata_billabstract_bill_id_ae9ce636_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billabstract_bill_id_ae9ce636_like ON public.opencivicdata_billabstract USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billaction_bill_id_32c574af; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billaction_bill_id_32c574af ON public.opencivicdata_billaction USING btree (bill_id);


--
-- Name: opencivicdata_billaction_bill_id_32c574af_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billaction_bill_id_32c574af_like ON public.opencivicdata_billaction USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billaction_organization_id_0f2653d0_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billaction_organization_id_0f2653d0_like ON public.opencivicdata_billactionrelatedentity USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_billaction_organization_id_16619b7f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billaction_organization_id_16619b7f ON public.opencivicdata_billaction USING btree (organization_id);


--
-- Name: opencivicdata_billaction_organization_id_16619b7f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billaction_organization_id_16619b7f_like ON public.opencivicdata_billaction USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_billactionrelatedentity_action_id_4f9a39ec; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billactionrelatedentity_action_id_4f9a39ec ON public.opencivicdata_billactionrelatedentity USING btree (action_id);


--
-- Name: opencivicdata_billactionrelatedentity_organization_id_0f2653d0; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billactionrelatedentity_organization_id_0f2653d0 ON public.opencivicdata_billactionrelatedentity USING btree (organization_id);


--
-- Name: opencivicdata_billactionrelatedentity_person_id_b1c818ff; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billactionrelatedentity_person_id_b1c818ff ON public.opencivicdata_billactionrelatedentity USING btree (person_id);


--
-- Name: opencivicdata_billactionrelatedentity_person_id_b1c818ff_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billactionrelatedentity_person_id_b1c818ff_like ON public.opencivicdata_billactionrelatedentity USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_billdocument_bill_id_6620b91a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billdocument_bill_id_6620b91a ON public.opencivicdata_billdocument USING btree (bill_id);


--
-- Name: opencivicdata_billdocument_bill_id_6620b91a_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billdocument_bill_id_6620b91a_like ON public.opencivicdata_billdocument USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billdocumentlink_document_id_6a555184; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billdocumentlink_document_id_6a555184 ON public.opencivicdata_billdocumentlink USING btree (document_id);


--
-- Name: opencivicdata_billidentifier_bill_id_7eb921fc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billidentifier_bill_id_7eb921fc ON public.opencivicdata_billidentifier USING btree (bill_id);


--
-- Name: opencivicdata_billidentifier_bill_id_7eb921fc_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billidentifier_bill_id_7eb921fc_like ON public.opencivicdata_billidentifier USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billsource_bill_id_832557ca; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsource_bill_id_832557ca ON public.opencivicdata_billsource USING btree (bill_id);


--
-- Name: opencivicdata_billsource_bill_id_832557ca_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsource_bill_id_832557ca_like ON public.opencivicdata_billsource USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billsponsorship_bill_id_c0161ea6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_bill_id_c0161ea6 ON public.opencivicdata_billsponsorship USING btree (bill_id);


--
-- Name: opencivicdata_billsponsorship_bill_id_c0161ea6_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_bill_id_c0161ea6_like ON public.opencivicdata_billsponsorship USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billsponsorship_organization_id_e2f034bd; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_organization_id_e2f034bd ON public.opencivicdata_billsponsorship USING btree (organization_id);


--
-- Name: opencivicdata_billsponsorship_organization_id_e2f034bd_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_organization_id_e2f034bd_like ON public.opencivicdata_billsponsorship USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_billsponsorship_person_id_c2295c47; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_person_id_c2295c47 ON public.opencivicdata_billsponsorship USING btree (person_id);


--
-- Name: opencivicdata_billsponsorship_person_id_c2295c47_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billsponsorship_person_id_c2295c47_like ON public.opencivicdata_billsponsorship USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_billtitle_bill_id_1534b245; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billtitle_bill_id_1534b245 ON public.opencivicdata_billtitle USING btree (bill_id);


--
-- Name: opencivicdata_billtitle_bill_id_1534b245_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billtitle_bill_id_1534b245_like ON public.opencivicdata_billtitle USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billversion_bill_id_33ab8294; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billversion_bill_id_33ab8294 ON public.opencivicdata_billversion USING btree (bill_id);


--
-- Name: opencivicdata_billversion_bill_id_33ab8294_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billversion_bill_id_33ab8294_like ON public.opencivicdata_billversion USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_billversionlink_version_id_51725693; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_billversionlink_version_id_51725693 ON public.opencivicdata_billversionlink USING btree (version_id);


--
-- Name: opencivicdata_division_id_0fbf8337_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_division_id_0fbf8337_like ON public.opencivicdata_division USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_division_redirect_id_6ef2b608; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_division_redirect_id_6ef2b608 ON public.opencivicdata_division USING btree (redirect_id);


--
-- Name: opencivicdata_division_redirect_id_6ef2b608_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_division_redirect_id_6ef2b608_like ON public.opencivicdata_division USING btree (redirect_id varchar_pattern_ops);


--
-- Name: opencivicdata_event_id_1e7b7d87_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_event_id_1e7b7d87_like ON public.opencivicdata_event USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_event_jurisdiction_id_c4e8bc4e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_event_jurisdiction_id_c4e8bc4e ON public.opencivicdata_event USING btree (jurisdiction_id);


--
-- Name: opencivicdata_event_jurisdiction_id_c4e8bc4e_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_event_jurisdiction_id_c4e8bc4e_like ON public.opencivicdata_event USING btree (jurisdiction_id varchar_pattern_ops);


--
-- Name: opencivicdata_event_jurisdiction_id_start_ti_d48530f5_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_event_jurisdiction_id_start_ti_d48530f5_idx ON public.opencivicdata_event USING btree (jurisdiction_id, start_date, name);


--
-- Name: opencivicdata_event_location_id_d9c073f4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_event_location_id_d9c073f4 ON public.opencivicdata_event USING btree (location_id);


--
-- Name: opencivicdata_eventagendaitem_event_id_560759f9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventagendaitem_event_id_560759f9 ON public.opencivicdata_eventagendaitem USING btree (event_id);


--
-- Name: opencivicdata_eventagendaitem_event_id_560759f9_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventagendaitem_event_id_560759f9_like ON public.opencivicdata_eventagendaitem USING btree (event_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventagendamedia_agenda_item_id_0af7ca3e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventagendamedia_agenda_item_id_0af7ca3e ON public.opencivicdata_eventagendamedia USING btree (agenda_item_id);


--
-- Name: opencivicdata_eventdocument_event_id_c3f037c7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventdocument_event_id_c3f037c7 ON public.opencivicdata_eventdocument USING btree (event_id);


--
-- Name: opencivicdata_eventdocument_event_id_c3f037c7_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventdocument_event_id_c3f037c7_like ON public.opencivicdata_eventdocument USING btree (event_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventlocation_coordinates_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventlocation_coordinates_id ON public.opencivicdata_eventlocation USING gist (coordinates);


--
-- Name: opencivicdata_eventlocation_jurisdiction_id_ba71aaa3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventlocation_jurisdiction_id_ba71aaa3 ON public.opencivicdata_eventlocation USING btree (jurisdiction_id);


--
-- Name: opencivicdata_eventlocation_jurisdiction_id_ba71aaa3_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventlocation_jurisdiction_id_ba71aaa3_like ON public.opencivicdata_eventlocation USING btree (jurisdiction_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventmedia_event_id_39421e7b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventmedia_event_id_39421e7b ON public.opencivicdata_eventmedia USING btree (event_id);


--
-- Name: opencivicdata_eventmedia_event_id_39421e7b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventmedia_event_id_39421e7b_like ON public.opencivicdata_eventmedia USING btree (event_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventparticipant_event_id_76328a2f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_event_id_76328a2f ON public.opencivicdata_eventparticipant USING btree (event_id);


--
-- Name: opencivicdata_eventparticipant_event_id_76328a2f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_event_id_76328a2f_like ON public.opencivicdata_eventparticipant USING btree (event_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventparticipant_organization_id_0a03b9a7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_organization_id_0a03b9a7 ON public.opencivicdata_eventparticipant USING btree (organization_id);


--
-- Name: opencivicdata_eventparticipant_organization_id_0a03b9a7_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_organization_id_0a03b9a7_like ON public.opencivicdata_eventparticipant USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventparticipant_person_id_28dc5e7c; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_person_id_28dc5e7c ON public.opencivicdata_eventparticipant USING btree (person_id);


--
-- Name: opencivicdata_eventparticipant_person_id_28dc5e7c_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventparticipant_person_id_28dc5e7c_like ON public.opencivicdata_eventparticipant USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventrelatedentity_agenda_item_id_7c739fc2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_agenda_item_id_7c739fc2 ON public.opencivicdata_eventrelatedentity USING btree (agenda_item_id);


--
-- Name: opencivicdata_eventrelatedentity_bill_id_5d6380d7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_bill_id_5d6380d7 ON public.opencivicdata_eventrelatedentity USING btree (bill_id);


--
-- Name: opencivicdata_eventrelatedentity_bill_id_5d6380d7_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_bill_id_5d6380d7_like ON public.opencivicdata_eventrelatedentity USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventrelatedentity_organization_id_0eaf6158; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_organization_id_0eaf6158 ON public.opencivicdata_eventrelatedentity USING btree (organization_id);


--
-- Name: opencivicdata_eventrelatedentity_organization_id_0eaf6158_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_organization_id_0eaf6158_like ON public.opencivicdata_eventrelatedentity USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventrelatedentity_person_id_c82ecc59; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_person_id_c82ecc59 ON public.opencivicdata_eventrelatedentity USING btree (person_id);


--
-- Name: opencivicdata_eventrelatedentity_person_id_c82ecc59_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_person_id_c82ecc59_like ON public.opencivicdata_eventrelatedentity USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_eventrelatedentity_vote_event_id_83e2a0e9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_vote_event_id_83e2a0e9 ON public.opencivicdata_eventrelatedentity USING btree (vote_event_id);


--
-- Name: opencivicdata_eventrelatedentity_vote_event_id_83e2a0e9_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_eventrelatedentity_vote_event_id_83e2a0e9_like ON public.opencivicdata_eventrelatedentity USING btree (vote_event_id varchar_pattern_ops);


--
-- Name: opencivicdata_jurisdiction_classification_5e7edfaf; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_jurisdiction_classification_5e7edfaf ON public.opencivicdata_jurisdiction USING btree (classification);


--
-- Name: opencivicdata_jurisdiction_classification_5e7edfaf_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_jurisdiction_classification_5e7edfaf_like ON public.opencivicdata_jurisdiction USING btree (classification varchar_pattern_ops);


--
-- Name: opencivicdata_jurisdiction_division_id_70d82947; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_jurisdiction_division_id_70d82947 ON public.opencivicdata_jurisdiction USING btree (division_id);


--
-- Name: opencivicdata_jurisdiction_division_id_70d82947_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_jurisdiction_division_id_70d82947_like ON public.opencivicdata_jurisdiction USING btree (division_id varchar_pattern_ops);


--
-- Name: opencivicdata_jurisdiction_id_fd0c1912_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_jurisdiction_id_fd0c1912_like ON public.opencivicdata_jurisdiction USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_legislativesession_jurisdiction_id_54141e1e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_legislativesession_jurisdiction_id_54141e1e ON public.opencivicdata_legislativesession USING btree (jurisdiction_id);


--
-- Name: opencivicdata_legislativesession_jurisdiction_id_54141e1e_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_legislativesession_jurisdiction_id_54141e1e_like ON public.opencivicdata_legislativesession USING btree (jurisdiction_id varchar_pattern_ops);


--
-- Name: opencivicdata_membership_id_c112492b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_id_c112492b_like ON public.opencivicdata_membership USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_membership_organization_id_bf51a2be; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_organization_id_bf51a2be ON public.opencivicdata_membership USING btree (organization_id);


--
-- Name: opencivicdata_membership_organization_id_bf51a2be_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_organization_id_bf51a2be_like ON public.opencivicdata_membership USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_membership_organization_id_person_i_d20901c6_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_organization_id_person_i_d20901c6_idx ON public.opencivicdata_membership USING btree (organization_id, person_id, post_id);


--
-- Name: opencivicdata_membership_person_id_b8541e5b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_person_id_b8541e5b ON public.opencivicdata_membership USING btree (person_id);


--
-- Name: opencivicdata_membership_person_id_b8541e5b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_person_id_b8541e5b_like ON public.opencivicdata_membership USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_membership_post_id_c7e554f4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_post_id_c7e554f4 ON public.opencivicdata_membership USING btree (post_id);


--
-- Name: opencivicdata_membership_post_id_c7e554f4_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_membership_post_id_c7e554f4_like ON public.opencivicdata_membership USING btree (post_id varchar_pattern_ops);


--
-- Name: opencivicdata_organizati_jurisdiction_id_classifi_3466801f_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organizati_jurisdiction_id_classifi_3466801f_idx ON public.opencivicdata_organization USING btree (jurisdiction_id, classification, name);


--
-- Name: opencivicdata_organization_classification_name_8008bbd6_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_classification_name_8008bbd6_idx ON public.opencivicdata_organization USING btree (classification, name);


--
-- Name: opencivicdata_organization_id_18cfc97b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_id_18cfc97b_like ON public.opencivicdata_organization USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_organization_jurisdiction_id_3d545d77; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_jurisdiction_id_3d545d77 ON public.opencivicdata_organization USING btree (jurisdiction_id);


--
-- Name: opencivicdata_organization_jurisdiction_id_3d545d77_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_jurisdiction_id_3d545d77_like ON public.opencivicdata_organization USING btree (jurisdiction_id varchar_pattern_ops);


--
-- Name: opencivicdata_organization_parent_id_8da063e7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_parent_id_8da063e7 ON public.opencivicdata_organization USING btree (parent_id);


--
-- Name: opencivicdata_organization_parent_id_8da063e7_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_organization_parent_id_8da063e7_like ON public.opencivicdata_organization USING btree (parent_id varchar_pattern_ops);


--
-- Name: opencivicdata_person_current_jurisdiction_id_67631021; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_person_current_jurisdiction_id_67631021 ON public.opencivicdata_person USING btree (current_jurisdiction_id);


--
-- Name: opencivicdata_person_current_jurisdiction_id_67631021_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_person_current_jurisdiction_id_67631021_like ON public.opencivicdata_person USING btree (current_jurisdiction_id varchar_pattern_ops);


--
-- Name: opencivicdata_person_id_42353458_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_person_id_42353458_like ON public.opencivicdata_person USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_person_name_663c152b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_person_name_663c152b ON public.opencivicdata_person USING btree (name);


--
-- Name: opencivicdata_person_name_663c152b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_person_name_663c152b_like ON public.opencivicdata_person USING btree (name varchar_pattern_ops);


--
-- Name: opencivicdata_personidentifier_person_id_4a59ae8e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personidentifier_person_id_4a59ae8e ON public.opencivicdata_personidentifier USING btree (person_id);


--
-- Name: opencivicdata_personidentifier_person_id_4a59ae8e_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personidentifier_person_id_4a59ae8e_like ON public.opencivicdata_personidentifier USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_personlink_person_id_b3a41b21; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personlink_person_id_b3a41b21 ON public.opencivicdata_personlink USING btree (person_id);


--
-- Name: opencivicdata_personlink_person_id_b3a41b21_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personlink_person_id_b3a41b21_like ON public.opencivicdata_personlink USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_personname_name_35448948; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personname_name_35448948 ON public.opencivicdata_personname USING btree (name);


--
-- Name: opencivicdata_personname_name_35448948_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personname_name_35448948_like ON public.opencivicdata_personname USING btree (name varchar_pattern_ops);


--
-- Name: opencivicdata_personname_person_id_89e987d1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personname_person_id_89e987d1 ON public.opencivicdata_personname USING btree (person_id);


--
-- Name: opencivicdata_personname_person_id_89e987d1_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personname_person_id_89e987d1_like ON public.opencivicdata_personname USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_personsource_person_id_d33c1559; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personsource_person_id_d33c1559 ON public.opencivicdata_personsource USING btree (person_id);


--
-- Name: opencivicdata_personsource_person_id_d33c1559_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personsource_person_id_d33c1559_like ON public.opencivicdata_personsource USING btree (person_id varchar_pattern_ops);


--
-- Name: opencivicdata_personvote_vote_event_id_7d507bb5; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personvote_vote_event_id_7d507bb5 ON public.opencivicdata_personvote USING btree (vote_event_id);


--
-- Name: opencivicdata_personvote_vote_event_id_7d507bb5_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personvote_vote_event_id_7d507bb5_like ON public.opencivicdata_personvote USING btree (vote_event_id varchar_pattern_ops);


--
-- Name: opencivicdata_personvote_voter_id_6740775f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personvote_voter_id_6740775f ON public.opencivicdata_personvote USING btree (voter_id);


--
-- Name: opencivicdata_personvote_voter_id_6740775f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personvote_voter_id_6740775f_like ON public.opencivicdata_personvote USING btree (voter_id varchar_pattern_ops);


--
-- Name: opencivicdata_personvote_voter_name_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_personvote_voter_name_idx ON public.opencivicdata_personvote USING btree (voter_name);


--
-- Name: opencivicdata_post_division_id_82fef8df; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_division_id_82fef8df ON public.opencivicdata_post USING btree (division_id);


--
-- Name: opencivicdata_post_division_id_82fef8df_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_division_id_82fef8df_like ON public.opencivicdata_post USING btree (division_id varchar_pattern_ops);


--
-- Name: opencivicdata_post_id_969c8af0_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_id_969c8af0_like ON public.opencivicdata_post USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_post_organization_id_7dab6fa7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_organization_id_7dab6fa7 ON public.opencivicdata_post USING btree (organization_id);


--
-- Name: opencivicdata_post_organization_id_7dab6fa7_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_organization_id_7dab6fa7_like ON public.opencivicdata_post USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_post_organization_id_label_8792a17f_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_post_organization_id_label_8792a17f_idx ON public.opencivicdata_post USING btree (organization_id, label);


--
-- Name: opencivicdata_relatedbill_bill_id_1a0b62e4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_relatedbill_bill_id_1a0b62e4 ON public.opencivicdata_relatedbill USING btree (bill_id);


--
-- Name: opencivicdata_relatedbill_bill_id_1a0b62e4_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_relatedbill_bill_id_1a0b62e4_like ON public.opencivicdata_relatedbill USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_relatedbill_related_bill_id_22d5e5eb; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_relatedbill_related_bill_id_22d5e5eb ON public.opencivicdata_relatedbill USING btree (related_bill_id);


--
-- Name: opencivicdata_relatedbill_related_bill_id_22d5e5eb_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_relatedbill_related_bill_id_22d5e5eb_like ON public.opencivicdata_relatedbill USING btree (related_bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_searchablebill_bill_id_1eb6303c_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_searchablebill_bill_id_1eb6303c_like ON public.opencivicdata_searchablebill USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_votecount_vote_event_id_f1f263f8; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_votecount_vote_event_id_f1f263f8 ON public.opencivicdata_votecount USING btree (vote_event_id);


--
-- Name: opencivicdata_votecount_vote_event_id_f1f263f8_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_votecount_vote_event_id_f1f263f8_like ON public.opencivicdata_votecount USING btree (vote_event_id varchar_pattern_ops);


--
-- Name: opencivicdata_voteevent_bill_id_ae459db1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_bill_id_ae459db1 ON public.opencivicdata_voteevent USING btree (bill_id);


--
-- Name: opencivicdata_voteevent_bill_id_ae459db1_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_bill_id_ae459db1_like ON public.opencivicdata_voteevent USING btree (bill_id varchar_pattern_ops);


--
-- Name: opencivicdata_voteevent_dedupe__75a90b_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_dedupe__75a90b_idx ON public.opencivicdata_voteevent USING btree (dedupe_key);


--
-- Name: opencivicdata_voteevent_id_c0d97a14_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_id_c0d97a14_like ON public.opencivicdata_voteevent USING btree (id varchar_pattern_ops);


--
-- Name: opencivicdata_voteevent_legislative_session_id_63ea1068; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_legislative_session_id_63ea1068 ON public.opencivicdata_voteevent USING btree (legislative_session_id);


--
-- Name: opencivicdata_voteevent_legislative_session_id_b_e48f547e_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_legislative_session_id_b_e48f547e_idx ON public.opencivicdata_voteevent USING btree (legislative_session_id, bill_id);


--
-- Name: opencivicdata_voteevent_legislative_session_id_i_3bb84db4_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_legislative_session_id_i_3bb84db4_idx ON public.opencivicdata_voteevent USING btree (legislative_session_id, identifier, bill_id);


--
-- Name: opencivicdata_voteevent_organization_id_d7bd0f84; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_organization_id_d7bd0f84 ON public.opencivicdata_voteevent USING btree (organization_id);


--
-- Name: opencivicdata_voteevent_organization_id_d7bd0f84_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_voteevent_organization_id_d7bd0f84_like ON public.opencivicdata_voteevent USING btree (organization_id varchar_pattern_ops);


--
-- Name: opencivicdata_votesource_vote_event_id_a670ce14; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_votesource_vote_event_id_a670ce14 ON public.opencivicdata_votesource USING btree (vote_event_id);


--
-- Name: opencivicdata_votesource_vote_event_id_a670ce14_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX opencivicdata_votesource_vote_event_id_a670ce14_like ON public.opencivicdata_votesource USING btree (vote_event_id varchar_pattern_ops);


--
-- Name: search_index; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX search_index ON public.opencivicdata_searchablebill USING gin (search_vector);


--
-- Name: opencivicdata_bill opencivicdata_bill_from_organization_id_e96ed21d_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_bill
    ADD CONSTRAINT opencivicdata_bill_from_organization_id_e96ed21d_fk_opencivic FOREIGN KEY (from_organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_bill opencivicdata_bill_legislative_session__ef50ac55_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_bill
    ADD CONSTRAINT opencivicdata_bill_legislative_session__ef50ac55_fk_opencivic FOREIGN KEY (legislative_session_id) REFERENCES public.opencivicdata_legislativesession(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billabstract opencivicdata_billab_bill_id_ae9ce636_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billabstract
    ADD CONSTRAINT opencivicdata_billab_bill_id_ae9ce636_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billactionrelatedentity opencivicdata_billac_action_id_4f9a39ec_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billactionrelatedentity
    ADD CONSTRAINT opencivicdata_billac_action_id_4f9a39ec_fk_opencivic FOREIGN KEY (action_id) REFERENCES public.opencivicdata_billaction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billaction opencivicdata_billac_bill_id_32c574af_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billaction
    ADD CONSTRAINT opencivicdata_billac_bill_id_32c574af_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billactionrelatedentity opencivicdata_billac_organization_id_0f2653d0_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billactionrelatedentity
    ADD CONSTRAINT opencivicdata_billac_organization_id_0f2653d0_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billaction opencivicdata_billac_organization_id_16619b7f_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billaction
    ADD CONSTRAINT opencivicdata_billac_organization_id_16619b7f_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billactionrelatedentity opencivicdata_billac_person_id_b1c818ff_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billactionrelatedentity
    ADD CONSTRAINT opencivicdata_billac_person_id_b1c818ff_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billdocument opencivicdata_billdo_bill_id_6620b91a_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billdocument
    ADD CONSTRAINT opencivicdata_billdo_bill_id_6620b91a_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billdocumentlink opencivicdata_billdo_document_id_6a555184_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billdocumentlink
    ADD CONSTRAINT opencivicdata_billdo_document_id_6a555184_fk_opencivic FOREIGN KEY (document_id) REFERENCES public.opencivicdata_billdocument(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billidentifier opencivicdata_billid_bill_id_7eb921fc_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billidentifier
    ADD CONSTRAINT opencivicdata_billid_bill_id_7eb921fc_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billsource opencivicdata_billso_bill_id_832557ca_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsource
    ADD CONSTRAINT opencivicdata_billso_bill_id_832557ca_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billsponsorship opencivicdata_billsp_bill_id_c0161ea6_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsponsorship
    ADD CONSTRAINT opencivicdata_billsp_bill_id_c0161ea6_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billsponsorship opencivicdata_billsp_organization_id_e2f034bd_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsponsorship
    ADD CONSTRAINT opencivicdata_billsp_organization_id_e2f034bd_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billsponsorship opencivicdata_billsp_person_id_c2295c47_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billsponsorship
    ADD CONSTRAINT opencivicdata_billsp_person_id_c2295c47_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billtitle opencivicdata_billti_bill_id_1534b245_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billtitle
    ADD CONSTRAINT opencivicdata_billti_bill_id_1534b245_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billversion opencivicdata_billve_bill_id_33ab8294_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billversion
    ADD CONSTRAINT opencivicdata_billve_bill_id_33ab8294_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_billversionlink opencivicdata_billve_version_id_51725693_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_billversionlink
    ADD CONSTRAINT opencivicdata_billve_version_id_51725693_fk_opencivic FOREIGN KEY (version_id) REFERENCES public.opencivicdata_billversion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_division opencivicdata_divisi_redirect_id_6ef2b608_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_division
    ADD CONSTRAINT opencivicdata_divisi_redirect_id_6ef2b608_fk_opencivic FOREIGN KEY (redirect_id) REFERENCES public.opencivicdata_division(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_event opencivicdata_event_jurisdiction_id_c4e8bc4e_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_event
    ADD CONSTRAINT opencivicdata_event_jurisdiction_id_c4e8bc4e_fk_opencivic FOREIGN KEY (jurisdiction_id) REFERENCES public.opencivicdata_jurisdiction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_event opencivicdata_event_location_id_d9c073f4_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_event
    ADD CONSTRAINT opencivicdata_event_location_id_d9c073f4_fk_opencivic FOREIGN KEY (location_id) REFERENCES public.opencivicdata_eventlocation(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventagendamedia opencivicdata_eventa_agenda_item_id_0af7ca3e_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventagendamedia
    ADD CONSTRAINT opencivicdata_eventa_agenda_item_id_0af7ca3e_fk_opencivic FOREIGN KEY (agenda_item_id) REFERENCES public.opencivicdata_eventagendaitem(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventagendaitem opencivicdata_eventa_event_id_560759f9_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventagendaitem
    ADD CONSTRAINT opencivicdata_eventa_event_id_560759f9_fk_opencivic FOREIGN KEY (event_id) REFERENCES public.opencivicdata_event(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventdocument opencivicdata_eventd_event_id_c3f037c7_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventdocument
    ADD CONSTRAINT opencivicdata_eventd_event_id_c3f037c7_fk_opencivic FOREIGN KEY (event_id) REFERENCES public.opencivicdata_event(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventlocation opencivicdata_eventl_jurisdiction_id_ba71aaa3_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventlocation
    ADD CONSTRAINT opencivicdata_eventl_jurisdiction_id_ba71aaa3_fk_opencivic FOREIGN KEY (jurisdiction_id) REFERENCES public.opencivicdata_jurisdiction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventmedia opencivicdata_eventm_event_id_39421e7b_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventmedia
    ADD CONSTRAINT opencivicdata_eventm_event_id_39421e7b_fk_opencivic FOREIGN KEY (event_id) REFERENCES public.opencivicdata_event(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventparticipant opencivicdata_eventp_event_id_76328a2f_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventparticipant
    ADD CONSTRAINT opencivicdata_eventp_event_id_76328a2f_fk_opencivic FOREIGN KEY (event_id) REFERENCES public.opencivicdata_event(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventparticipant opencivicdata_eventp_organization_id_0a03b9a7_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventparticipant
    ADD CONSTRAINT opencivicdata_eventp_organization_id_0a03b9a7_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventparticipant opencivicdata_eventp_person_id_28dc5e7c_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventparticipant
    ADD CONSTRAINT opencivicdata_eventp_person_id_28dc5e7c_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventr_agenda_item_id_7c739fc2_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventr_agenda_item_id_7c739fc2_fk_opencivic FOREIGN KEY (agenda_item_id) REFERENCES public.opencivicdata_eventagendaitem(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventr_bill_id_5d6380d7_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventr_bill_id_5d6380d7_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventr_organization_id_0eaf6158_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventr_organization_id_0eaf6158_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventr_person_id_c82ecc59_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventr_person_id_c82ecc59_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_eventrelatedentity opencivicdata_eventr_vote_event_id_83e2a0e9_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_eventrelatedentity
    ADD CONSTRAINT opencivicdata_eventr_vote_event_id_83e2a0e9_fk_opencivic FOREIGN KEY (vote_event_id) REFERENCES public.opencivicdata_voteevent(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_jurisdiction opencivicdata_jurisd_division_id_70d82947_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_jurisdiction
    ADD CONSTRAINT opencivicdata_jurisd_division_id_70d82947_fk_opencivic FOREIGN KEY (division_id) REFERENCES public.opencivicdata_division(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_legislativesession opencivicdata_legisl_jurisdiction_id_54141e1e_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_legislativesession
    ADD CONSTRAINT opencivicdata_legisl_jurisdiction_id_54141e1e_fk_opencivic FOREIGN KEY (jurisdiction_id) REFERENCES public.opencivicdata_jurisdiction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_membership opencivicdata_member_organization_id_bf51a2be_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_membership
    ADD CONSTRAINT opencivicdata_member_organization_id_bf51a2be_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_membership opencivicdata_member_person_id_b8541e5b_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_membership
    ADD CONSTRAINT opencivicdata_member_person_id_b8541e5b_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_membership opencivicdata_member_post_id_c7e554f4_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_membership
    ADD CONSTRAINT opencivicdata_member_post_id_c7e554f4_fk_opencivic FOREIGN KEY (post_id) REFERENCES public.opencivicdata_post(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_organization opencivicdata_organi_jurisdiction_id_3d545d77_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_organization
    ADD CONSTRAINT opencivicdata_organi_jurisdiction_id_3d545d77_fk_opencivic FOREIGN KEY (jurisdiction_id) REFERENCES public.opencivicdata_jurisdiction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_organization opencivicdata_organi_parent_id_8da063e7_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_organization
    ADD CONSTRAINT opencivicdata_organi_parent_id_8da063e7_fk_opencivic FOREIGN KEY (parent_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_person opencivicdata_person_current_jurisdiction_67631021_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_person
    ADD CONSTRAINT opencivicdata_person_current_jurisdiction_67631021_fk_opencivic FOREIGN KEY (current_jurisdiction_id) REFERENCES public.opencivicdata_jurisdiction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personidentifier opencivicdata_person_person_id_4a59ae8e_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personidentifier
    ADD CONSTRAINT opencivicdata_person_person_id_4a59ae8e_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personname opencivicdata_person_person_id_89e987d1_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personname
    ADD CONSTRAINT opencivicdata_person_person_id_89e987d1_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personlink opencivicdata_person_person_id_b3a41b21_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personlink
    ADD CONSTRAINT opencivicdata_person_person_id_b3a41b21_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personsource opencivicdata_person_person_id_d33c1559_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personsource
    ADD CONSTRAINT opencivicdata_person_person_id_d33c1559_fk_opencivic FOREIGN KEY (person_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personvote opencivicdata_person_vote_event_id_7d507bb5_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personvote
    ADD CONSTRAINT opencivicdata_person_vote_event_id_7d507bb5_fk_opencivic FOREIGN KEY (vote_event_id) REFERENCES public.opencivicdata_voteevent(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_personvote opencivicdata_person_voter_id_6740775f_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_personvote
    ADD CONSTRAINT opencivicdata_person_voter_id_6740775f_fk_opencivic FOREIGN KEY (voter_id) REFERENCES public.opencivicdata_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_post opencivicdata_post_division_id_82fef8df_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_post
    ADD CONSTRAINT opencivicdata_post_division_id_82fef8df_fk_opencivic FOREIGN KEY (division_id) REFERENCES public.opencivicdata_division(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_post opencivicdata_post_organization_id_7dab6fa7_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_post
    ADD CONSTRAINT opencivicdata_post_organization_id_7dab6fa7_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_relatedbill opencivicdata_relate_bill_id_1a0b62e4_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_relatedbill
    ADD CONSTRAINT opencivicdata_relate_bill_id_1a0b62e4_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_relatedbill opencivicdata_relate_related_bill_id_22d5e5eb_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_relatedbill
    ADD CONSTRAINT opencivicdata_relate_related_bill_id_22d5e5eb_fk_opencivic FOREIGN KEY (related_bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_searchablebill opencivicdata_search_bill_id_1eb6303c_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill
    ADD CONSTRAINT opencivicdata_search_bill_id_1eb6303c_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_searchablebill opencivicdata_search_version_link_id_151ca538_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_searchablebill
    ADD CONSTRAINT opencivicdata_search_version_link_id_151ca538_fk_opencivic FOREIGN KEY (version_link_id) REFERENCES public.opencivicdata_billversionlink(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_votecount opencivicdata_voteco_vote_event_id_f1f263f8_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_votecount
    ADD CONSTRAINT opencivicdata_voteco_vote_event_id_f1f263f8_fk_opencivic FOREIGN KEY (vote_event_id) REFERENCES public.opencivicdata_voteevent(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_voteevent opencivicdata_voteev_bill_action_id_a4847ddd_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteev_bill_action_id_a4847ddd_fk_opencivic FOREIGN KEY (bill_action_id) REFERENCES public.opencivicdata_billaction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_voteevent opencivicdata_voteev_bill_id_ae459db1_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteev_bill_id_ae459db1_fk_opencivic FOREIGN KEY (bill_id) REFERENCES public.opencivicdata_bill(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_voteevent opencivicdata_voteev_legislative_session__63ea1068_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteev_legislative_session__63ea1068_fk_opencivic FOREIGN KEY (legislative_session_id) REFERENCES public.opencivicdata_legislativesession(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_voteevent opencivicdata_voteev_organization_id_d7bd0f84_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_voteevent
    ADD CONSTRAINT opencivicdata_voteev_organization_id_d7bd0f84_fk_opencivic FOREIGN KEY (organization_id) REFERENCES public.opencivicdata_organization(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: opencivicdata_votesource opencivicdata_voteso_vote_event_id_a670ce14_fk_opencivic; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.opencivicdata_votesource
    ADD CONSTRAINT opencivicdata_voteso_vote_event_id_a670ce14_fk_opencivic FOREIGN KEY (vote_event_id) REFERENCES public.opencivicdata_voteevent(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: TABLE opencivicdata_bill; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_bill TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_bill TO openstates_fdw;


--
-- Name: TABLE opencivicdata_billabstract; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billabstract TO cbwinslow;


--
-- Name: TABLE opencivicdata_billaction; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billaction TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_billaction TO openstates_fdw;


--
-- Name: TABLE opencivicdata_billactionrelatedentity; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billactionrelatedentity TO cbwinslow;


--
-- Name: TABLE opencivicdata_billdocument; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billdocument TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_billdocument TO openstates_fdw;


--
-- Name: TABLE opencivicdata_billdocumentlink; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billdocumentlink TO cbwinslow;


--
-- Name: TABLE opencivicdata_billidentifier; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billidentifier TO cbwinslow;


--
-- Name: TABLE opencivicdata_billsource; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billsource TO cbwinslow;


--
-- Name: TABLE opencivicdata_billsponsorship; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billsponsorship TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_billsponsorship TO openstates_fdw;


--
-- Name: TABLE opencivicdata_billtitle; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billtitle TO cbwinslow;


--
-- Name: TABLE opencivicdata_billversion; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billversion TO cbwinslow;


--
-- Name: TABLE opencivicdata_billversionlink; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_billversionlink TO cbwinslow;


--
-- Name: TABLE opencivicdata_division; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_division TO cbwinslow;


--
-- Name: TABLE opencivicdata_event; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_event TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventagendaitem; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventagendaitem TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventagendamedia; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventagendamedia TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventdocument; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventdocument TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventlocation; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventlocation TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventmedia; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventmedia TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventparticipant; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventparticipant TO cbwinslow;


--
-- Name: TABLE opencivicdata_eventrelatedentity; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_eventrelatedentity TO cbwinslow;


--
-- Name: TABLE opencivicdata_jurisdiction; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_jurisdiction TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_jurisdiction TO openstates_fdw;


--
-- Name: TABLE opencivicdata_legislativesession; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_legislativesession TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_legislativesession TO openstates_fdw;


--
-- Name: TABLE opencivicdata_membership; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_membership TO cbwinslow;


--
-- Name: TABLE opencivicdata_organization; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_organization TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_organization TO openstates_fdw;


--
-- Name: TABLE opencivicdata_person; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_person TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_person TO openstates_fdw;


--
-- Name: TABLE opencivicdata_personidentifier; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_personidentifier TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_personidentifier TO openstates_fdw;


--
-- Name: TABLE opencivicdata_personlink; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_personlink TO cbwinslow;


--
-- Name: TABLE opencivicdata_personname; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_personname TO cbwinslow;


--
-- Name: TABLE opencivicdata_personsource; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_personsource TO cbwinslow;


--
-- Name: TABLE opencivicdata_personvote; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_personvote TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_personvote TO openstates_fdw;


--
-- Name: TABLE opencivicdata_post; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_post TO cbwinslow;


--
-- Name: TABLE opencivicdata_relatedbill; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_relatedbill TO cbwinslow;


--
-- Name: TABLE opencivicdata_searchablebill; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_searchablebill TO cbwinslow;


--
-- Name: SEQUENCE opencivicdata_searchablebill_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.opencivicdata_searchablebill_id_seq TO cbwinslow;


--
-- Name: TABLE opencivicdata_votecount; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_votecount TO cbwinslow;


--
-- Name: TABLE opencivicdata_voteevent; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_voteevent TO cbwinslow;
GRANT SELECT ON TABLE public.opencivicdata_voteevent TO openstates_fdw;


--
-- Name: TABLE opencivicdata_votesource; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.opencivicdata_votesource TO cbwinslow;


--
-- PostgreSQL database dump complete
--

\unrestrict opendiscourseschemasnapshot
