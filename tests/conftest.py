from __future__ import annotations

import os


REQUIRED_ENV_DEFAULTS = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "offer_automation_test",
    "DB_USER": "offer_user",
    "DB_PASSWORD": "change_me",
    "DB_SSL_MODE": "disable",
    "SECURITY_SECRET_KEY": "change_me",
    "SECURITY_API_TOKEN": "change_me",
    "SHOPEE_APP_ID": "change_me",
    "SHOPEE_APP_SECRET": "change_me",
    "SHOPEE_BASE_URL": "https://open-api.affiliate.shopee.com.br",
    "TELEGRAM_BOT_TOKEN": "dummy-token",
    "TELEGRAM_CHAT_ID": "dummy-chat",
    "X_API_KEY": "dummy-api-key",
    "X_API_SECRET": "dummy-api-secret",
    "X_ACCESS_TOKEN": "dummy-access-token",
    "X_ACCESS_SECRET": "dummy-access-secret",
}


for key, value in REQUIRED_ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
