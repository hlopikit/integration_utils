from django.conf import settings
from integration_utils.vendors.telegram.bot import Bot

def log_to_telegram(text):
    """
    исползьзует настройки из settings.py
    TELEGRAM_LOG_BOT_TOKEN = '20933333:AAHUF233232323AA_DmGewfw332r32r0UI9qk'
    TELEGRAM_LOG_CHAT_ID = -38283832832832

    :param text:
    :return:
    """

    try:
        Bot(token=settings.TELEGRAM_LOG_BOT_TOKEN).send_message(settings.TELEGRAM_LOG_CHAT_ID, text)
        return True
    except Exception:
        return False



