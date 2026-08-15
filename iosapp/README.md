GolfCoachNow - FastAPI service for wedge engine processing

## Payments

Stripe checkout, webhook handling and unlock logic live in `payments/`. The
package is self contained: the only thing it adds outside that folder is one
`include_router` call in `server.py`. The wedge engine and the video pipeline
are untouched.

- [docs/PAYMENTS.md](docs/PAYMENTS.md) - endpoints, unlock logic, and the contract the mobile app is written against
- [docs/TESTING.md](docs/TESTING.md) - running a real test payment end to end
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - going live, plus a support runbook

### Setup

    pip install -r requirements-dev.txt
    cp .env.example .env
    alembic upgrade head

Fill in `.env` before starting the app. Every variable is described in
`.env.example`. The settings are validated at startup, so a missing key stops
the process on boot rather than surfacing later on a live payment.

### Tests

    pytest

No network access and no Stripe keys needed. The suite covers signature
verification, the idempotency guarantees, and the response shapes the mobile
app depends on.
