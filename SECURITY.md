# Security Policy

Google Health Agent handles sensitive personal data in private deployments. Public issues must
never include OAuth credentials, bearer tokens, health records, private endpoints, logs with
secrets, or screenshots containing personal information.

For a suspected vulnerability, use GitHub private vulnerability reporting after the public
repository enables it. Until then, do not publish exploit details or secrets in an issue.

Supported security properties in Phase 1:

- synthetic-only public tests and fixtures;
- read-only health MCP tools;
- localhost default binding;
- mandatory authentication for non-loopback configuration;
- encrypted Google OAuth token storage;
- bounded queries and no arbitrary SQL, shell, file, or HTTP tools;
- secret scanning in local checks and CI;
- no telemetry by default.

This software is not a medical device. Security reports should focus on confidentiality,
integrity, authentication, authorization, and availability rather than medical interpretation.

