# Resumable runners

FRED metadata indexing stores no observations and resumes from
`catalog.discovery`. Run one worker at a time.

```bash
# One bounded batch
research-db sync --source fred --index --pages 20

# Work for 30 minutes, then exit cleanly with the cursor saved
research-db sync --source fred --index --minutes 30

# Inspect cursor, totals, and state
research-db status
```

Optional systemd templates are in `ops/systemd/`; they are not installed by
the project. To enable them for the current user, copy both files into
`~/.config/systemd/user/`, then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now opendiscourse-fred.timer
systemctl --user list-timers opendiscourse-fred.timer
```

The timer has an hourly schedule with a randomized five-minute delay. Disable
it with `systemctl --user disable --now opendiscourse-fred.timer`.
