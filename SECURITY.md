# Security

## Reporting a vulnerability

Please report security issues privately rather than in a public issue:
open a [security advisory](https://github.com/MartexHACK/trading-bot/security/advisories/new)
on this repository.

Especially interested in anything that could:

- expose or exfiltrate API keys or credentials,
- cause an unintended real-money order,
- bypass the risk guard or its KILLED latch,
- allow remote access to the dashboard.

## Handling credentials

- **Never commit API keys.** `config/secrets/`, `*.key`, `*.pem`, and `.env`
  are gitignored, and the release build refuses to ship a wheel containing
  them.
- Exchange and broker keys should be scoped to trading only. **Never enable
  withdrawal permission** on a key used by automated software.
- IP-allowlist your keys where the exchange supports it.
- If you fork this repository, check your own history before making it
  public.

## The dashboard

The dashboard binds to `127.0.0.1` only and has **no authentication**. It is
a local operations view, not a web application. Do not expose it through a
reverse proxy, a tunnel, or a `0.0.0.0` bind — anyone who reaches it can read
your trading state.

## Live trading

Real-money execution is deliberately gated:

- it is not reachable from the CLI or the dashboard,
- it requires your own broker adapter and credentials,
- it requires a deliberate command-line action,
- the risk guard's KILLED latch can only be cleared by a human.

Please do not remove these gates, and treat a pull request that weakens them
as a security issue.

## Scope

This is research software provided with no warranty (see `LICENSE`) and it is
not audited. Running it against real money is entirely at your own risk — see
`DISCLAIMER.md`.
