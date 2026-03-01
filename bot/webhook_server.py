"""
Webhook server for payment providers (CryptoBot, etc).
Runs on separate port for async webhook handling.
"""

import logging
import json
import hmac
import hashlib
from aiohttp import web
from typing import Dict, Any

from config.settings import settings
from bot.handlers.payment_handlers import process_cryptobot_webhook

logger = logging.getLogger(__name__)


# ============================================================================
# CRYPTOBOT WEBHOOK HANDLER
# ============================================================================

async def cryptobot_webhook_handler(request: web.Request) -> web.Response:
    """
    Handle CryptoBot webhook requests.

    CryptoBot sends POST requests with:
    - payload: JSON string with invoice data
    - signature: HMAC SHA256 signature

    Expected format:
    {
        "update_type": "invoice_paid",
        "payload": "123",  # Our payment ID
        "invoice_id": "456",
        "status": "paid",
        "amount": "10.00",
        "asset": "USDT",
        ...
    }
    """
    try:
        # Get request data
        payload = await request.text()
        signature = request.headers.get("Crypto-Pay-Signature", "")

        logger.debug(f"Received CryptoBot webhook: payload={payload[:100]}, signature={signature[:20]}...")

        # Parse JSON
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in webhook: {payload[:100]}")
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

        # Process webhook
        result = await process_cryptobot_webhook(data, signature)

        if result.get("ok"):
            return web.json_response({"ok": True})
        else:
            logger.error(f"Webhook processing failed: {result.get('error')}")
            return web.json_response(result, status=400)

    except Exception as e:
        logger.error(f"Webhook handler error: {e}", exc_info=True)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ============================================================================
# WEBHOOK SERVER
# ============================================================================

async def create_webhook_app() -> web.Application:
    """Create aiohttp application for webhook handling."""
    app = web.Application()

    # CryptoBot webhook endpoint
    app.router.add_post("/webhook/cryptobot", cryptobot_webhook_handler)

    # Health check
    async def health_check(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "payment-webhook"})

    app.router.add_get("/health", health_check)

    return app


async def start_webhook_server(port: int = 8081):
    """Start webhook server on specified port."""
    app = await create_webhook_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Webhook server started on port {port}")
    logger.info(f"CryptoBot webhook: http://your-server:{port}/webhook/cryptobot")

    return runner


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO)

        runner = await start_webhook_server(8081)

        try:
            # Keep server running
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Shutting down webhook server...")
        finally:
            await runner.cleanup()

    asyncio.run(main())
