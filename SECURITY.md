# Security policy

## Scope

Gastei is a single-user personal finance application designed to run on a user's own machine or private infrastructure. It is **not** intended to be exposed publicly. The threat model assumes the user has sole control of the machine; multi-tenant or hostile-network deployments are out of scope.

## Reporting a vulnerability

If you find a security issue, **please do not open a public GitHub issue**. Email the maintainer (guilhermebarradasdev@gmail.com) or open a private security advisory through GitHub's "Security" tab.

Please include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof-of-concept.
- Your assessment of severity and any mitigations.

I aim to respond within 5 business days and to publish a fix or mitigation within 30 days for confirmed issues.

## Handling secrets

- `.env` is gitignored. **Never commit it.**
- `SECRET_KEY` is a Fernet key used to encrypt sensitive fields. Generate with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- API keys for LLM providers, Pluggy, and other integrations live in `.env` and should be rotated immediately if leaked.
- Logs must never include API keys, full account numbers, CPF, or amounts tied to identifiable individuals. The logging configuration in `src/gastei/utils/logging.py` applies redaction helpers.

## Deployment guidance

- Bind the API to `localhost` for development; place a reverse proxy with TLS in front for any remote access.
- Prefer **Tailscale** or **Cloudflare Tunnel** over public exposure with basic auth.
- Apply Fly.io / Railway secret management when deploying — see [`DEPLOY.md`](./DEPLOY.md).
- Rate-limit the LLM and bank-sync endpoints if exposing to anyone but yourself.

## Dependencies

Dependencies are pinned in `uv.lock`. Run `uv lock --upgrade` periodically and review the resulting diff. The CI workflow (`.github/workflows/ci.yml`) runs `pytest` on every push; consider adding `pip-audit` or `safety check` in a follow-up if dependency vulnerabilities become a concern.

## Known limitations

- The LLM provider sees transaction descriptions in clear text. If your bank statements contain sensitive merchant names, consider using a local model (e.g. Ollama with `qwen2.5:14b`) instead of a hosted provider.
- The chat agent has access to tools that read your entire transaction history. The system prompt restricts it from sharing PII verbatim, but treat the chat as it were a user with full read access to the database.
