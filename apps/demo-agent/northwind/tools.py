from praetor_sdk import governed


@governed("lookup_kb")
def lookup_kb(query: str) -> dict[str, str]:
    return {
        "query": query,
        "answer": "Northwind orders can only be discussed with verified customer contacts.",
    }


@governed("send_email")
def send_email(recipient: str, subject: str, body: str) -> dict[str, str]:
    return {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "status": "queued",
    }


@governed("issue_refund")
def issue_refund(amount: float, account: str) -> dict[str, str | float]:
    return {
        "amount": amount,
        "account": account,
        "status": "pending_review",
    }
