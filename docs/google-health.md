# Google Health API v4

The provider targets `https://health.googleapis.com/v4` and never calls the legacy Fitbit Web
API. Technical behavior follows the current official
[Google Health endpoint guide](https://developers.google.com/health/endpoints),
[data point list reference](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list),
[data type reference](https://developers.google.com/health/data-types), and
[scope reference](https://developers.google.com/health/scopes).

## OAuth

Private deployments use Google's
[Web Server Authorization Code Flow](https://developers.google.com/identity/protocols/oauth2/web-server).
`/oauth/google-health/login` creates a single-use state value and redirects with
`access_type=offline`; `/oauth/google-health/callback` validates state, exchanges the code
server-side, encrypts tokens, and returns no token to the browser.

Only these scopes are requested:

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
```

No write or modify scope is present. Tokens are encrypted with a Fernet key provided through
`GOOGLE_TOKEN_ENCRYPTION_KEY`; tokens and authorization codes are never logged.

## Requests and normalization

The provider calls
`GET /v4/users/me/dataTypes/{dataType}/dataPoints`, uses official AIP-160 date filters, follows
`nextPageToken`, and stores source/platform/recording method with each point. Physical UTC
timestamps, the reported UTC offset, and civil date are preserved separately so travel is not
interpreted using server timezone.

429 and retryable 5xx responses use bounded exponential backoff. A single 401 can trigger an
offline refresh. Structured errors cover permission denial, missing data types, rate limits,
timeouts, malformed responses, and unavailable service.

All Phase 2A provider integration tests use mocked HTTP. Real consent, tokens, accounts, and
health data require separate Phase 2B authorization. The first real import, if later authorized,
must expand gradually: a minimal smoke test, 1–3 days, 7 days, 30 days, then 90 days. It must not
begin with an unbounded or full-history download.
