-- One vote sync at a time. A session-level advisory lock: it ends with the connection that took it.
SELECT pg_try_advisory_lock(hashtextextended(%(key)s, 0)) AS acquired;
