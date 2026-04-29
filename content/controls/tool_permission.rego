package praetor.controls.tool_permission

default decision := {
  "allow": true,
  "outcome": "allow",
  "rationale": "tool call is within hot-path policy",
}

deny_external_recipient if {
  input.tool == "send_email"
  recipient := input.args.recipient
  domain := lower(split(recipient, "@")[1])
  not domain == "northwind.test"
  not domain == "customer.example"
}

deny_prompt_injection if {
  input.tool == "send_email"
  content := lower(sprintf("%s %s", [input.args.subject, input.args.body]))
  regex.match("ignore previous|jailbreak|reset system", content)
}

decision := {
  "allow": false,
  "outcome": "deny",
  "rationale": "recipient domain is not allowlisted",
} if deny_external_recipient

decision := {
  "allow": false,
  "outcome": "deny",
  "rationale": "email content matches prompt-injection refusal pattern",
} if deny_prompt_injection
