# Security notes

This repository is an **educational demo**. Do not deploy it to untrusted public users as-is.

- Never commit `.env`, credentials, screenshots containing keys, real trip data or local PostgreSQL dumps.
- Rotate any API keys and database passwords that may have been revealed in previous project drafts.
- `user_id` is a display label, **not authentication**. Add authentication and per-user authorization to checkpoint access before deployment.
- MCP stdio servers execute third-party Python code as subprocesses. Install only from reviewed sources. Inspect tool results for untrusted content.
- `mcp_client.py` passes the Tavily key as the provider-specified URL parameter. Treat full URLs as secrets; do not print or log them.
- The application does not make purchases. No real trip should be booked without provider confirmation.
- The budget validator verifies mathematical consistency of **user-entered** price data; it does not verify the provider's price or a real lowest fare.
- The text guardrail is a limited defensive filter; it cannot catch every hallucinated implication. Use structured output and broader evaluations before production use.
- User-generated PDFs can contain private travel details and are excluded from Git.

If you discover a vulnerability in your fork, do not post secrets in a public issue. Use GitHub's private vulnerability reporting feature where supported.
