# Rebuild workflow matrix

| Need | Source of truth | Safe next step |
|---|---|---|
| Fresh local database | `docs/getting-started.md` | Configure `.env`, choose Docker or bare metal, then run `uv run research-db init-db`. |
| Overall rebuild scope | `_bmad-output/specs/spec-rebuild-kit/SPEC.md` | Read the capability and constraint before choosing a source. |
| Per-source coverage and known gaps | `_bmad-output/specs/spec-rebuild-kit/source-matrix.md` | Use the stated command only if its gap is closed or the operator explicitly scopes a bounded proof. |
| Current operational state | `docs/PROJECT-STATE.md`, `inventory/progress.yaml` | Prefer current code/tests when they disagree with a handoff. |
| New or changed source workflow | `opendiscourse-connector` and `opendiscourse-provenance` | Build through the Connector lifecycle; do not add central dispatcher branches. |
| Source-specific traps | A narrow project skill | Add one only after a repeated format, identity, capacity, or resume risk is proven. |

## External plugin gate

An external plugin is packaging, not a new runtime. Publish only after a clean
checkout on an independent machine or isolated environment can: configure
`DATA_ROOT` and database settings without exposing secrets; initialize the
database; run a read-only source-status path; execute the relevant verification
checks; and, for any transfer workflow, pass capacity review, explicit approval,
resume, and provenance checks. Keep application logic in the repository.
