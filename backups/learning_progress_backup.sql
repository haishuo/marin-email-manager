--
-- PostgreSQL database dump
--

-- Dumped from database version 14.17 (Homebrew)
-- Dumped by pg_dump version 14.17 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: learning_progress; Type: TABLE DATA; Schema: public; Owner: marin_user
--

COPY public.learning_progress (id, total_classifications, last_training_batch, next_training_threshold, tier0_rules_count, tier1_model_version, tier23_examples_count, last_updated) FROM stdin;
1	0	0	300	0	\N	0	2025-06-30 14:36:20.627684-04
\.


--
-- Name: learning_progress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: marin_user
--

SELECT pg_catalog.setval('public.learning_progress_id_seq', 1, true);


--
-- PostgreSQL database dump complete
--

