# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hiddify VPN Telegram Bot with role-based access control, invite system, and Hiddify Manager API integration. Production server: **kodu-3xui** (5.45.114.73).

**Current Version**: v4.0.0 (PostgreSQL + Redis + Payment System)
**Status**: Development (Migration from v3.1.1)
**Bot**: @SKRTvpnbot

### v4.0.0 New Features:
- **PostgreSQL** instead of SQLite (with Alembic migrations)
- **Redis** for caching (profiles, subscriptions, configs)
- **Stripe** payment integration
- **Support tickets** system
- **Referral** program
- **Config Builder** (Standard/Enhanced modes)
- **Prometheus + Grafana** monitoring
- **Health check** endpoints

---

## Development Commands

### Testing
```bash
# Run all tests
pytest tests/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/integration/test_invite_flow.py -v

# Run with coverage
pytest tests/ --cov=scripts --cov-report=html
```

### Database Operations
```bash
# Admin CLI on server
ssh kodu-3xui "cd /opt/hiddify-manager && python3 scripts/db_admin.py"

# Local database inspection
sqlite3 data/bot.db "SELECT telegram_id, role FROM users LIMIT 5;"
sqlite3 data/bot.db "SELECT * FROM invites WHERE is_active = 1;"
```

### Code Quality
```bash
# Lint (if flake8 is installed)
flake8 scripts/ --max-line-length=120

# Type checking (if mypy is installed)
mypy scripts/
```

---

## Architecture

### Core Components

**`scripts/monitor_bot.py`** (2000+ lines)
- Main Telegram bot using aiogram + telebot hybrid
- FSM for user states
- Admin panel with user management
- Inline keyboard handlers
- Entry point: `if __name__ == "__main__": main()`

**`scripts/hiddify_api.py`**
- `HiddifyAPI` class for Hiddify Manager API
- Invite system functions: `use_invite_code()`, `create_invite_code()`, `validate_invite_code()`
- **Critical**: `use_invite_code()` uses atomic UPDATE to prevent race conditions
- **Validation**: `create_invite_code()` validates format (INV_xxx), max_uses (1-1000), user existence

**`scripts/roles.py`** (v3.1+)
- Role enum: USER, MANAGER, ADMIN
- `can_invite_users(telegram_id)` - checks if user can create invites
- `get_user_role(telegram_id)` - returns role from database
- Graceful degradation: returns True if module unavailable

**`scripts/database/`** (v3.1.1+)
- `connection.py`: Database singleton with thread-local connections + WAL mode
- `models.py`: Pydantic validation models (InviteCodeCreate, InviteCodeResponse, Payment*, SupportTicket*, Referral*, Subscription*)

**`scripts/cache/`** (v4.0+)
- `redis_client.py`: Redis client for caching profiles, subscriptions, configs

**`scripts/payments/`** (v4.0+)
- `stripe_client.py`: Stripe payment integration
- `promo_client.py`: Promo code system

**`scripts/support/`** (v4.0+)
- `ticket_manager.py`: Support tickets management

**`scripts/referral/`** (v4.0+)
- `referral_manager.py`: Referral program

**`scripts/config/`** (v4.0+)
- `standard_builder.py`: Standard VLESS config generator
- `enhanced_builder.py`: Enhanced VLESS config generator with Fragment

**`scripts/monitoring/`** (v4.0+)
- `metrics.py`: Prometheus metrics
- `health.py`: Health check endpoints

### Database Schema

#### SQLite (v3.1.1 - Legacy)

**Table: users**
- `telegram_id` (unique) - Telegram user ID
- `role` (TEXT) - 'user', 'manager', 'admin' (v3.1+)
- `invite_code` (TEXT, unique) - Personal invite code
- `invited_by` (INT) - Who invited them
- `data_limit_bytes`, `expires_at`, `used_bytes`
- `is_trial`, `trial_expiry`, `trial_activated`

**Table: invites**
- `code` (TEXT, unique) - Format: INV_ + hex chars (e.g., INV_abc12345)
- `created_by` (INT) - telegram_id of creator
- `max_uses` (INT) - Maximum uses (1-1000)
- `used_count` (INT) - Current usage count
- `is_active` (BOOLEAN) - Auto-deactivated when limit reached
- `expires_at` (TIMESTAMP) - Optional expiration

**WAL Mode Enabled**:
```sql
PRAGMA journal_mode=WAL;  -- Enabled for concurrent access
PRAGMA busy_timeout=30000;
PRAGMA foreign_keys=ON;
```

#### PostgreSQL (v4.0+ - Production)

**New Tables**:
- `subscriptions` - User subscriptions with auto-renewal
- `payments` - Payment records (Stripe, crypto, promos)
- `support_tickets` - Support tickets with categories
- `ticket_messages` - Ticket conversation history
- `referrals` - Referral program records
- `promo_codes` - Promo codes with usage limits
- `promo_usage` - Promo code usage tracking

**Migration**: Use `scripts/migrate_to_postgres.py --dry-run` first, then `--migrate`

---

## v4.0 New Patterns

### Redis Caching
Always cache frequently accessed data:
```python
from scripts.cache.redis_client import redis_client

# Get from cache or DB
profile = await redis_client.get_user_profile(telegram_id)
if not profile:
    profile = await get_user_from_db(telegram_id)
    await redis_client.set_user_profile(telegram_id, profile)

# Invalidate on update
await redis_client.invalidate_user_profile(telegram_id)
```

### Payment Flow
```python
from scripts.payments.stripe_client import stripe_client
from scripts.database.models import PaymentCreate, PaymentMethod

payment = PaymentCreate(
    user_id=telegram_id,
    amount=Decimal("10.00"),
    currency="USD",
    method=PaymentMethod.CARD,
    plan_code="monthly"
)

result = await stripe_client.create_checkout_session(
    payment=payment,
    success_url="https://t.me/bot?start=payment_success",
    cancel_url="https://t.me/bot?start=payment_cancel"
)

# Send result.checkout_url to user
```

### Support Tickets
```python
from scripts.support.ticket_manager import ticket_manager
from scripts.database.models import SupportTicketCreate, TicketCategory

ticket = SupportTicketCreate(
    user_id=telegram_id,
    category=TicketCategory.CONNECTION,
    title="Не подключается",
    description="Проблема с соединением..."
)

result = await ticket_manager.create_ticket(ticket)
```

---

## Critical Patterns

### Race Condition Prevention
When using invite codes, ALWAYS use the atomic `use_invite_code()` function:
```python
from scripts.hiddify_api import use_invite_code

result = use_invite_code(db_path, invite_code)
# Returns: {'success': bool, 'message': str, 'invite_data': dict|None}
```

DO NOT manually update `used_count` - this causes race conditions.

### Role-Based Access
Check permissions before allowing invite creation:
```python
from scripts.roles import can_invite_users

if not can_invite_users(telegram_id):
    return "У вас нет прав для создания инвайт-кодов"
```

### Graceful Degradation
All role checks should be wrapped in try/except:
```python
try:
    from scripts.roles import can_invite_users
    if not can_invite_users(telegram_id):
        return "Недостаточно прав"
except ImportError:
    # Fallback: allow all if roles module unavailable
    pass
```

### Invite Code Format
Invite codes MUST follow format: `INV_` + 8-50 hex characters [a-f0-9]
```python
# Valid: INV_abc12345, INV_deadbeef
# Invalid: INV_valid, INV_TEST123 (contains non-hex)
```

---

## Deployment

### Server: kodu-3xui (5.45.114.73)

**v3.1.1 Deployment (Legacy - SQLite)**:
```bash
# SSH access
ssh kodu-3xui
# Password in ~/.mcp-env (KODU_3XUI_PASSWORD)

# Deploy after git push
ssh kodu-3xui << 'EOF'
cd /opt/hiddify-manager
git pull
systemctl restart hiddify-bot.service
systemctl status hiddify-bot.service --no-pager | head -10
EOF
```

**v4.0 Deployment (Docker + PostgreSQL)**:
```bash
# Deploy with Docker Compose
SERVER_HOST=kodu-3xui bash scripts/deploy-docker.sh

# Manual deployment
ssh kodu-3xui
cd /opt/hiddify-manager/infrastructure/docker
docker-compose up -d postgres redis telegram-bot prometheus grafana
docker-compose logs -f telegram-bot
```

### Path on Server
- **Project**: `/opt/hiddify-manager/`
- **Docker Compose**: `/opt/hiddify-manager/infrastructure/docker/docker-compose.yml`
- **Virtualenv**: `/opt/hiddify-manager/venv/` (legacy)
- **Database**: PostgreSQL in Docker (v4.0) or `/opt/hiddify-manager/data/bot.db` (v3.x)
- **Service**: `hiddify-bot.service` (legacy) or Docker containers (v4.0)

### Post-Deploy Checklist

**v3.1.1**:
1. Service status: `systemctl is-active hiddify-bot.service`
2. Check logs for errors: `journalctl -u hiddify-bot.service -n 50`
3. Test basic functionality via Telegram
4. Verify WAL mode: `sqlite3 /opt/hiddify-manager/data/bot.db "PRAGMA journal_mode;"`

**v4.0**:
1. Containers status: `docker-compose ps`
2. Health check: `curl http://localhost:8080/health`
3. Check logs: `docker-compose logs -f telegram-bot`
4. Prometheus: `http://localhost:9091`
5. Grafana: `http://localhost:3000`

---

## Environment Variables

### v3.1.1 (Legacy)
```bash
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_ADMIN_ID=<your Telegram ID>
PANEL_DOMAIN=<Hiddify panel domain>
HIDDIFY_API_TOKEN=<from Hiddify panel>
VPS_IP=<server IP>
REALITY_PUBLIC_KEY=<X25519 public key>
REALITY_SNI=<SNI domain, e.g., www.apple.com>
```

### v4.0 (New Variables)
```bash
# PostgreSQL
DATABASE_URL=postgresql://hiddify_user:password@localhost:5432/hiddify_bot
POSTGRES_DB=hiddify_bot
POSTGRES_USER=hiddify_user
POSTGRES_PASSWORD=change_me_in_production
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=change_me_in_production
REDIS_PORT=6379

# Stripe Payments
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

# Monitoring
METRICS_PORT=9090
HEALTH_PORT=8080
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=change_me_in_production
PROMETHEUS_PORT=9091
GRAFANA_PORT=3000
```

**NEVER commit `.env`** - it's in `.gitignore`.

---

## Version History Context

- **v4.0.0** (2026-02-27): PostgreSQL, Redis, Stripe payments, Support tickets, Referrals, Config Builder, Monitoring
- **v3.1.1+db** (2026-02-26): Race condition fixes, WAL mode, Pydantic validation
- **v3.1.1** (2026-02-26): Invite restrictions by role (MANAGER/ADMIN only)
- **v3.1.0** (2026-02-26): Role system (USER/MANAGER/ADMIN)
- **v3.0.0** (2026-02-26): Full refactor, admin panel, Hiddify API integration
- **v2.2.0**: QR codes, platform instructions, trial periods

---

## File Structure Notes

### New in v4.0:
- **`infrastructure/docker/`**: Docker Compose configuration
- **`scripts/cache/`**: Redis caching module
- **`scripts/payments/`**: Stripe payment integration
- **`scripts/support/`**: Support tickets system
- **`scripts/referral/`**: Referral program
- **`scripts/config/`**: Standard/Enhanced config builders
- **`scripts/monitoring/`**: Prometheus metrics and health checks
- **`alembic/`**: Database migrations for PostgreSQL
- **`tests/unit/`**: Unit tests for new modules

### Existing:
- **`tests/integration/`**: Full integration tests with database fixtures
- **`tests/test_v311_invite_restriction.py`**: Role-based invite access tests
- **`docs/`**: Feature specifications and release notes
- **`configs/`**: Protocol configurations (VLESS-Reality, Hysteria2, SS-2022)
- **`scripts/deploy.sh`**: Legacy deployment script
- **`scripts/deploy-docker.sh`**: Docker deployment script (v4.0)
- **`scripts/migrate_to_v31.py`**: Database migration for role system
- **`scripts/migrate_to_postgres.py`**: SQLite → PostgreSQL migration (v4.0)

---

## Quick Context Restoration

Use these phrases to quickly restore project context:
- "продолжим работу над vpn"
- "продолжаем разработку ВПН сервиса"
- "вернёмся к vpn боту"

See `SESSION.md` for complete project history and current status.
