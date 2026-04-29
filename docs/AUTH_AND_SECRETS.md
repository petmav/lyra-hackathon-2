# Auth And Secret Management

Praetor now has a production-capable auth and secret boundary while preserving demo defaults.

## API Auth Modes

- `PRAETOR_AUTH_MODE=dev_bearer` keeps the local demo behavior: requests must send `Authorization: Bearer $DEV_BEARER`.
- `PRAETOR_AUTH_MODE=jwt` requires an HS256 JWT in the `Authorization` header.
- `PRAETOR_AUTH_MODE=disabled` is only intended for isolated local development.

JWT settings:

- `PRAETOR_JWT_SECRET`: shared HS256 verification secret.
- `PRAETOR_JWT_ISSUER`: optional required `iss` claim.
- `PRAETOR_JWT_AUDIENCE`: optional required `aud` claim.
- `PRAETOR_JWT_REQUIRED_READ_ROLE`: default `viewer`.
- `PRAETOR_JWT_REQUIRED_WRITE_ROLE`: default `operator`.

Roles can come from `roles`, `role`, `groups`, `scope`, or `scp` claims. Role hierarchy is `viewer < operator < admin`.

For internal workers and the web client, prefer:

- `PRAETOR_API_TOKEN` for backend-to-backend calls.
- `NEXT_PUBLIC_API_TOKEN` for the browser-facing frontend token.

The older `DEV_BEARER` and `NEXT_PUBLIC_DEV_BEARER` names still work for demo compatibility.

## Secret Backends

`auth_ref` values such as `secret:github_token` are resolved through one backend selected by `PRAETOR_SECRET_BACKEND`:

- `env`: resolve from environment variables.
- `vault`: resolve from HashiCorp Vault KV v2.
- `env_then_vault`: prefer env, then Vault.
- `vault_then_env`: prefer Vault, then env.

Vault settings:

- `VAULT_ADDR`: Vault base URL.
- `VAULT_TOKEN`: Vault token.
- `VAULT_NAMESPACE`: optional Enterprise namespace.
- `VAULT_KV_MOUNT`: KV v2 mount, default `secret`.
- `PRAETOR_VAULT_PATH_PREFIX`: path prefix, default `praetor`.

For `secret:github_token`, Praetor reads KV v2 path `secret/data/praetor/github_token` by default and accepts any of these fields in the returned secret data: `value`, `token`, `api_key`, `secret`, or the mapped environment key such as `GITHUB_TOKEN`.

Model provider keys can also come from Vault via:

- `secret:openai_api_key`
- `secret:anthropic_api_key`
- `secret:google_api_key`
