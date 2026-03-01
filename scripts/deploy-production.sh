#!/bin/bash
#
# Production Deployment Script for Hiddify Bot v5.0.0
# Deploys Aiogram 3 bot with PostgreSQL, payments, and monitoring
#

set -e  # Exit on error

echo "🚀 Hiddify Bot v5.0.0 - Production Deployment"
echo "=========================================="

# Configuration
SERVER="root@5.45.114.73"  # kodu-3xui server
SERVER_PATH="/opt/hiddify-manager/infrastructure/docker"
BOT_CONTAINER="telegram-bot"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# SSH команда с логированием
ssh_exec() {
    sshpass -p P8mFfFvE3d92d3Ln ssh $SERVER "$@"
}

echo ""
echo "📋 Step 1: Commit and push latest code"
echo "---------------------------------------"

git push origin main

echo "✅ Code pushed to origin/main"

echo ""
echo "📋 Step 2: Backup PostgreSQL database"
echo "-------------------------------------"

ssh_exec << 'EOF'
cd $SERVER_PATH
TIMESTAMP=`date +%Y%m%d_%H%M%S`
BACKUP_FILE="backups/hiddify_bot_\${TIMESTAMP}.sql"

mkdir -p backups
docker-compose exec -T postgres pg_dump -U hiddify_user hiddify_db > \$BACKUP_FILE
echo "✅ Backup created: \$BACKUP_FILE"
ls -lh \$BACKUP_FILE
EOF

echo ""
echo "📋 Step 3: Pull latest code on server"
echo "----------------------------------"

ssh_exec << 'EOF'
cd /opt/hiddify-manager
git fetch origin
git checkout main
git pull origin main
echo "✅ Code updated"
EOF

echo ""
echo "📋 Step 4: Rebuild and restart bot"
echo "--------------------------------"

ssh_exec << 'EOF'
cd $SERVER_PATH

# Stop containers
docker-compose stop telegram-bot 2>/dev/null || true

# Rebuild bot image
docker-compose build telegram-bot

# Start bot
docker-compose up -d telegram-bot

# Wait for bot to start
sleep 5
EOF

echo "✅ Bot rebuilt and restarted"

echo ""
echo "📋 Step 5: Run database migration (optional)"
echo "-----------------------------------------------"

read -p "Run SQLite → PostgreSQL migration? (y/N): " run_migration

if [[ $run_migration == "y" || $run_migration == "Y" ]]; then
    log_info "🔄 Running migration..."

    ssh_exec << 'EOF'
cd /opt/hiddify-manager
python scripts/migrate_sqlite_to_postgres.py
EOF

    echo "✅ Migration completed"
else
    log_warn "⏭️ Migration skipped"
fi

echo ""
echo "📋 Step 6: Check bot status"
echo "---------------------------"

ssh_exec << 'EOF'
cd $SERVER_PATH
echo "📊 Container status:"
docker-compose ps

echo ""
echo "📋 Bot logs (last 30 lines):"
docker-compose logs --tail=30 telegram-bot
EOF

echo ""
echo "📋 Step 7: Verify services"
echo "-------------------------"

# Check health endpoint
if curl -sf http://5.45.114.73:8080/health > /dev/null 2>&1; then
    log_info "✅ Health check OK"
else
    log_warn "⚠️  Health check failed (may need webhook server start)"
fi

# Check webhook port
if curl -sf http://5.45.114.73:8081/health > /dev/null 2>&1; then
    log_info "✅ Webhook server OK"
else
    log_warn "⚠️  Webhook check failed (may not be started yet)"
fi

echo ""
echo "=========================================="
echo "🎉 Deployment completed successfully!"
echo "=========================================="
echo ""
echo "🔗 Check bot: @SKRTvpnbot"
echo "📊 Metrics: http://5.88.114.73:9090/metrics"
echo "📈 Prometheus: http://5.45.114.73:9091"
echo "📊 Grafana: http://5.45.114.73:3000"
echo ""
echo "📝 Useful commands:"
echo "   ssh $SERVER"
echo "   cd $SERVER_PATH"
echo "   docker-compose logs -f telegram-bot"
echo "   docker-compose ps"
echo ""
