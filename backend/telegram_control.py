"""Resolve the configured Control group without falling back to a random chat."""
import os


def control_chat_id(allowed):
    explicit = os.getenv('TELEGRAM_CONTROL_CHAT_ID', '').strip()
    if explicit:
        return explicit if explicit in allowed else None
    for candidate in ('-5273638075', '-1004462729383'):
        if candidate in allowed:
            return candidate
    return None
