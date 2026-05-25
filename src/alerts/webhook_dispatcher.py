import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_RECEIVER_EMAIL
)

logger = logging.getLogger(__name__)

def dispatch_telegram_alert(anomaly_type: str, symbol: str, detected_val: float, threshold_val: float, description: str) -> bool:
    """
    Dispatches a markdown-formatted risk alert message to a Telegram Channel.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info(f"Telegram alerting not configured. Alert payload: {symbol} - {anomaly_type}")
        return False

    emoji_map = {
        "FLASH_CRASH": "🔴",
        "EXCESSIVE_VOLATILITY": "⚠️",
        "STATISTICAL_CRASH": "📉",
        "DEFAULT": "🚨"
    }
    emoji = emoji_map.get(anomaly_type, emoji_map["DEFAULT"])

    message = (
        f"{emoji} *CoinDCX Market Risk Alert* {emoji}\n\n"
        f"*Asset Symbol:* #{symbol}\n"
        f"*Alert Trigger:* `{anomaly_type}`\n"
        f"*Detected Value:* `{detected_val:.4f}`\n"
        f"*Threshold Limit:* `{threshold_val:.4f}`\n\n"
        f"*Risk Details:*\n_{description}_\n\n"
        f"🕒 _System Time: {logging.Formatter.default_time_format}_"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram risk alert dispatched successfully for {symbol} ({anomaly_type}).")
            return True
        else:
            logger.error(f"Telegram API responded with error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to transmit Telegram webhook for {symbol}: {e}")
        return False

def dispatch_email_alert(anomaly_type: str, symbol: str, detected_val: float, threshold_val: float, description: str) -> bool:
    """
    Transmits an operational alert notice directly to the risk desk email using SMTP.
    """
    if not SMTP_USER or not SMTP_PASS or not ALERT_RECEIVER_EMAIL:
        logger.info(f"SMTP alerting not configured. Alert payload: {symbol} - {anomaly_type}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 CoinDCX ALERT: {anomaly_type} for {symbol}"
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_RECEIVER_EMAIL

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 20px;">
        <div style="background-color: #0f172a; color: #ffffff; padding: 15px; border-radius: 6px 6px 0 0;">
          <h2 style="margin: 0; color: #ff5a00;">CoinDCX Market Risk Alert</h2>
        </div>
        <div style="background-color: #ffffff; padding: 20px; border-radius: 0 0 6px 6px; border: 1px solid #e2e8f0;">
          <p>An operational risk anomaly has been flagged by the automated pipeline:</p>
          <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <tr style="background-color: #f8fafc;">
              <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #cbd5e1;">Target Asset:</td>
              <td style="padding: 10px; border-bottom: 1px solid #cbd5e1;">{symbol}</td>
            </tr>
            <tr>
              <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #cbd5e1;">Anomaly Type:</td>
              <td style="padding: 10px; border-bottom: 1px solid #cbd5e1;">{anomaly_type}</td>
            </tr>
            <tr style="background-color: #f8fafc;">
              <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #cbd5e1;">Detected Value:</td>
              <td style="padding: 10px; border-bottom: 1px solid #cbd5e1;">{detected_val:.6f}</td>
            </tr>
            <tr>
              <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #cbd5e1;">Threshold Limit:</td>
              <td style="padding: 10px; border-bottom: 1px solid #cbd5e1;">{threshold_val:.6f}</td>
            </tr>
          </table>
          <div style="margin-top: 20px; padding: 15px; background-color: #ffe4e6; border-left: 5px style='solid' #991b1b; color: #991b1b; border-radius: 4px;">
            <strong>System Description:</strong><br/>
            {description}
          </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_RECEIVER_EMAIL, msg.as_string())
            logger.info(f"SMTP risk alert email successfully sent to {ALERT_RECEIVER_EMAIL} for {symbol}.")
            return True
    except Exception as e:
        logger.error(f"Failed to transmit SMTP mail alert for {symbol}: {e}")
        return False

def dispatch_all_channels(anomaly_type: str, symbol: str, detected_val: float, threshold_val: float, description: str) -> bool:
    """
    Dispatches notifications across all configured communication channels concurrently.
    """
    tg_status = dispatch_telegram_alert(anomaly_type, symbol, detected_val, threshold_val, description)
    email_status = dispatch_email_alert(anomaly_type, symbol, detected_val, threshold_val, description)
    return tg_status or email_status
