# Production Keys And Readiness

Praetor production mode is intentionally empty of demo records. To make agent workflows and external hooks live, fill the env vars in `infra/compose/.env.production.example`, then start the stack with `docker compose -f infra/compose/docker-compose.yml up -d --build`.

## Agent Model Providers

- `OPENAI_API_KEY` enables `provider=openai`.
- `ANTHROPIC_API_KEY` enables `provider=anthropic`.
- `GOOGLE_API_KEY` enables `provider=google`.
- `DEFAULT_MODEL_PROVIDER` and `DEFAULT_MODEL_NAME` choose the default model used when a workflow run does not specify one.
- `PRAETOR_AGENT_MODEL_MODE=auto` calls the live provider when its key exists and records a dry-run call otherwise.
- `PRAETOR_AGENT_MODEL_MODE=live` makes missing or failing provider calls fail the agent step.
- `PRAETOR_AGENT_MODEL_MODE=dry_run` never calls external model APIs.

Check readiness:

```bash
curl -H "Authorization: Bearer dev" http://localhost:8000/runtime/readiness
curl -H "Authorization: Bearer dev" http://localhost:8000/models/readiness
```

Run a live provider smoke test after adding a key:

```bash
curl -X POST http://localhost:8000/models:check \
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","model":"gpt-5.4-mini","live":true}'
```

## JSON Stack Integration Secrets

JSON Stack hooks use `auth_ref` names in manifests and resolve them through environment variables at call time. Dry-run previews never require a token.

- `secret:azure_devops_token` -> `AZURE_DEVOPS_TOKEN`
- `secret:confluence_oauth` -> `CONFLUENCE_OAUTH_TOKEN`
- `secret:datadog_api_key` -> `DATADOG_API_KEY`
- `secret:github_token` -> `GITHUB_TOKEN`
- `secret:gitlab_token` -> `GITLAB_TOKEN`
- `secret:google_drive_oauth` -> `GOOGLE_DRIVE_OAUTH_TOKEN`
- `secret:jira_oauth` -> `JIRA_OAUTH_TOKEN`
- `secret:linear_token` -> `LINEAR_TOKEN`
- `secret:microsoft_graph_oauth` -> `MICROSOFT_GRAPH_TOKEN`
- `secret:notion_token` -> `NOTION_TOKEN`
- `secret:okta_oauth` -> `OKTA_TOKEN`
- `secret:onetrust_oauth` -> `ONETRUST_TOKEN`
- `secret:power_platform_oauth` -> `POWER_PLATFORM_TOKEN`
- `secret:salesforce_oauth` -> `SALESFORCE_TOKEN`
- `secret:servicenow_oauth` -> `SERVICENOW_TOKEN`
- `secret:slack_bot_token` -> `SLACK_BOT_TOKEN`
- `secret:splunk_hec_token` -> `SPLUNK_HEC_TOKEN`
- `secret:zendesk_token` -> `ZENDESK_TOKEN`

Non-dry-run calls return `status=failed` and `error=missing-secret` when the matching env var is not present. Secret values are never included in readiness or hook-call responses.
