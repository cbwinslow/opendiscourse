-- One Voteview sync at a time. The lock ends when its connection closes.
SELECT pg_try_advisory_lock(hashtextextended(%(key)s, 0)) AS acquired;
