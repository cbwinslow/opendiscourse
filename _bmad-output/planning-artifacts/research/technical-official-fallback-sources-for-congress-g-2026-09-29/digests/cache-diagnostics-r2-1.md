# Cache-diagnostics digest — round 2

Accessed: 2026-09-29. Researcher received no project context.

- **Clearing a local cache cannot repair an origin-server failure** (high
  confidence). It can help only when a browser replays a stored bad response
  or has broken local application state. HTTP defines 500 as an unexpected
  server condition. Sources: [RFC 9110 server errors](https://www.rfc-editor.org/rfc/rfc9110.html#name-server-error-5xx)
  and [section 15.6.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-500-internal-server-error).
- **A 500 is not normally cacheable by default, but explicit cache directives,
  Service Worker storage, or an intermediary can still affect a browser-only
  result** (high confidence). Sources: [RFC 9110 cacheability](https://www.rfc-editor.org/rfc/rfc9110.html#status.code.cacheability),
  [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111.html#caching.negotiated.responses),
  and [Chrome DevTools cache guidance](https://developer.chrome.com/blog/devtools-tips-36).
- **Safe diagnosis is a low-rate, read-only GET comparison** (high confidence):
  preserve timestamp/status/selected headers and a redacted short body, then
  repeat with browser cache disabled or `Cache-Control: no-cache`. Do not use
  HEAD as the primary comparison, do not add arbitrary cache-busting query
  parameters, and do not retain credentials/cookies in logs. Sources:
  [RFC 9111 no-cache](https://www.rfc-editor.org/rfc/rfc9111.html#name-no-cache),
  [RFC 9110 safe methods](https://www.rfc-editor.org/rfc/rfc9110.html#safe.methods),
  [Chrome HAR/privacy guidance](https://developer.chrome.com/docs/devtools/settings/preferences).
