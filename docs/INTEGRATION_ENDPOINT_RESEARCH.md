# Integration Endpoint Research

Current outbound remediation dispatch is intentionally provider-neutral. GitHub is one destination, but Praetor proposed changes can also become tickets, messages, emails, or GRC records.

Checked endpoint shapes on 2026-04-29:

- GitHub REST pull requests: `POST https://api.github.com/repos/{owner}/{repo}/pulls`.
  Source: https://docs.github.com/en/rest/pulls?apiVersion=2026-03-10
- Jira Cloud issue creation: `POST https://{site}.atlassian.net/rest/api/3/issue`.
  Source: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- Linear GraphQL issue creation: `POST https://api.linear.app/graphql` with `issueCreate`.
  Source: https://linear.app/developers/graphql
- Microsoft Graph mail: `POST https://graph.microsoft.com/v1.0/me/sendMail`.
  Source: https://learn.microsoft.com/graph/api/user-sendmail?view=graph-rest-1.0
- Slack Web API messages: `POST https://slack.com/api/chat.postMessage`.
  Source: https://api.slack.com/methods/chat.postMessage
- ServiceNow table record creation: `POST https://{instance}.service-now.com/api/now/v1/table/{tableName}`.
  Source: https://www.servicenow.com/docs/r/xanadu/api-reference/rest-api-explorer/t_GetStartedCreateInt.html

Implementation mapping:

- `github_json/create_pull_request`
- `jira_json/create_issue`
- `linear_json/create_issue`
- `microsoft_mail_json/send_mail`
- `slack_json/post_message`
- `servicenow_grc_json/create_issue`

All of these are effectful external writes, so production non-dry-run calls are gated by approval and proposed-change dispatch additionally requires a sandbox run.
