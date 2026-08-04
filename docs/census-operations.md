# Census bulk operations

## Daily operator check

Run the read-only report before approving a package or investigating a refresh:

```bash
research-db census-health
```

`healthy` means every artifact required by a loaded plan is registered and its
canonical rows retain artifact lineage. `attention` means an operator decision
or planned lifecycle step is still needed. `failed` requires investigation; do
not widen or edit a loaded plan to recover.

## Metadata refresh

`censusmeta` is the only scheduled Census plan. It refreshes API/package
metadata and does not download or load bulk data:

```bash
research-db plan-run censusmeta
research-db census-health
```

To install the optional user-level weekly timer, copy both
`ops/systemd/opendiscourse-census-metadata.*` files to
`~/.config/systemd/user/`, then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now opendiscourse-census-metadata.timer
systemctl --user list-timers opendiscourse-census-metadata.timer
```

## Bulk recovery

Use a plan only at its present lifecycle state. A `.part` file resumes a
download; `downloaded` permits staging; `staged` permits canonical loading.
For a wider DHC scope, a new PEP vintage, or a new TIGER boundary vintage,
write and approve a new plan. Never edit a loaded plan.
