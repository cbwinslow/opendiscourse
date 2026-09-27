# Prompt for the next session

Resume OpenDiscourse on `feat/source-completion`. Read `AGENTS.md`, `docs/PROJECT-STATE.md`, and `docs/SESSION-HANDOFF-2026-09-27.md` first.

Find a safe, official solution for five Congress.gov HTTP 500 gaps without rerunning the full 106–107 bill download or using legacy local caches. The missing detail rows are 107 H.R. 2842 and H.R. 2843. The missing cosponsor lists are 106 S. 1378, 106 S.Res. 218, and 107 H.R. 5346.

First make read-only checks of the API and public pages. Investigate whether official list, action, title, subject, committee, summary, text, or other child endpoints can support retained evidence for an explicitly partial record. Do not invent fields, name-match people, or call partial data complete. If no official fallback exists, retain the named failures and write a bounded retry/fallback BMAD spec. Do not start unrelated sources or run a full `sync-congress-bills` pass.
