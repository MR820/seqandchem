# SeqChem external uptime Worker

Cron-only Cloudflare Worker that checks the public site and API every 5 minutes
from outside the production host, and sends a Feishu message on state changes.

Checks per run:

- `GET https://seqandchem.com/health` (HTTP 200, `ok`, `formats > 0`)
- `GET https://api.seqandchem.com/health` (HTTP 200, `ok`, `formats > 0`)
- `POST https://api.seqandchem.com/api/v1/convert` (`smi` → `inchi`, `CCO`)

It writes `state`, `last_check`, `last_result` and `last_alert` to the
`seqchem_uptime` KV namespace under the single key `status`. Alerts are sent on
OK → DOWN and DOWN → OK, with a repeat reminder every 6 hours while down.

Deployment status (2026-11-17):

- Worker: `seqchem-uptime`
- KV namespace: `seqchem_uptime` (created or reused by `deploy.sh`)
- Schedule: `*/5 * * * *`
- workers.dev subdomain: `seqchem` (required by Cloudflare for cron schedules)
- The Worker has no `fetch` handler, so it does not answer HTTP requests; there
  is no public `/check` endpoint.

## Required token permissions

The deployment token must be scoped to your Cloudflare account and include:

- Workers Scripts: Read + Write
- Workers KV Storage: Read + Write

Workers Scripts Write covers the script upload, secret upload and cron schedule.
No zone routes or DNS records are created.

## Deploy with a token you create

1. In the Cloudflare dashboard create an API token with the permissions above.
2. Put it in `~/.cloudflare-api.env` as `CLOUDFLARE_WORKERS_TOKEN=...` (mode 600).
3. Set the deployment variables (the repo contains no credentials):

   ```bash
   export CLOUDFLARE_ACCOUNT_ID=...
   export SEQCHEM_HOST=...
   export SEQCHEM_SSH_KEY=...
   ```

4. Run:

   ```bash
   ./load-feishu-secrets.sh
   ./deploy.sh
   ```

5. Wait for the first 5-minute cron run, then read the KV `status` key through
   the Cloudflare dashboard or API (`last_check`, `state`, `last_result`).

## Deploy with a temporary token

If your account only has a user-level "Create Additional Tokens" token that
cannot access Workers, create a temporary account-scoped token with the
permissions above, use it for the deployment, and delete it immediately. This
needs explicit user approval.

## Endpoint

There is no HTTP endpoint. The Worker only implements the `scheduled` handler,
so the workers.dev subdomain exists solely to satisfy Cloudflare's cron
requirement. Verify runs through the KV `status` key.
