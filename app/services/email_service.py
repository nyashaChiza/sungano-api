import httpx
from app.core.config import settings
from typing import Dict, Any
import json


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
) -> bool:
    """
    Send email using Mailjet API
    """
    if not settings.MAILJET_API_KEY or not settings.MAILJET_SECRET_KEY:
        print(f"[DEBUG] Email disabled - would send to {to_email}: {subject}")
        return True

    url = "https://api.mailjet.com/v3.1/send"

    payload = {
        "Messages": [
            {
                "From": {
                    "Email": settings.MAILJET_FROM_EMAIL,
                    "Name": settings.MAILJET_FROM_NAME,
                },
                "To": [
                    {
                        "Email": to_email,
                        "Name": to_name,
                    }
                ],
                "Subject": subject,
                "HTMLPart": html_content,
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
            )
        return response.status_code == 200
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


async def send_otp_email(
    email: str,
    otp_code: str,
    type: str,  # verify_phone, verify_email, reset_password
    user_name: str = "",
) -> bool:
    """
    Send OTP verification email
    """
    if type == "verify_email":
        subject = "Verify your Sungano email"
        title = "Email Verification"
        message = "Use this code to verify your email address"
    elif type == "verify_phone":
        subject = "Verify your Sungano phone number"
        title = "Phone Verification"
        message = "Use this code to verify your phone number"
    elif type == "reset_password":
        subject = "Reset your Sungano password"
        title = "Password Reset"
        message = "Use this code to reset your password"
    else:
        return False

    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                <h2 style="color: #333;">{title}</h2>
                <p style="color: #666; font-size: 16px;">{message}:</p>
                <div style="background-color: #f0f0f0; padding: 20px; border-radius: 8px; text-align: center;">
                    <p style="font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 5px; margin: 0;">{otp_code}</p>
                </div>
                <p style="color: #999; font-size: 14px; margin-top: 20px;">This code expires in 10 minutes.</p>
                <p style="color: #999; font-size: 12px;">If you didn't request this, you can safely ignore this email.</p>
            </div>
        </body>
    </html>
    """

    return await send_email(email, user_name, subject, html)


async def send_payment_notification(
    recipient_email: str,
    payer_name: str,
    amount: str,
    round_name: str,
    currency: str = "USD",
) -> bool:
    """
    Notify recipient of payment received
    """
    subject = f"Payment received in {round_name}"
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                <h2 style="color: #28a745;">Payment Received</h2>
                <p style="color: #666; font-size: 16px;"><strong>{payer_name}</strong> has submitted a payment in <strong>{round_name}</strong>.</p>
                <div style="background-color: #f0f0f0; padding: 20px; border-radius: 8px; text-align: center;">
                    <p style="font-size: 24px; font-weight: bold; color: #28a745; margin: 0;">{currency} {amount}</p>
                </div>
                <p style="color: #666; margin-top: 20px;">Please review and confirm the payment in the app. You have 72 hours to confirm.</p>
                <a href="{settings.FRONTEND_URL}" style="display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 20px;">Open Sungano</a>
            </div>
        </body>
    </html>
    """
    return await send_email(recipient_email, "", subject, html)


async def send_default_notice(
    user_email: str,
    user_name: str,
    round_name: str,
    amount: str,
    currency: str = "USD",
) -> bool:
    """
    Notify user of payment default
    """
    subject = f"Default notification - {round_name}"
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                <h2 style="color: #dc3545;">Payment Default</h2>
                <p style="color: #666; font-size: 16px;">Hi {user_name},</p>
                <p style="color: #666; font-size: 16px;">You have not submitted your payment of <strong>{currency} {amount}</strong> for <strong>{round_name}</strong> within the grace period.</p>
                <p style="color: #dc3545; font-weight: bold;">This has been recorded as a default on your Sungano account and may affect your trust score.</p>
                <p style="color: #666; margin-top: 20px;">Take action now to prevent further impact:</p>
                <a href="{settings.FRONTEND_URL}" style="display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 20px;">Submit Payment</a>
            </div>
        </body>
    </html>
    """
    return await send_email(user_email, user_name, subject, html)


async def send_reminder(
    user_email: str,
    user_name: str,
    reminder_type: str,
    payload: Dict[str, Any],
) -> bool:
    """
    Send reminder based on type
    Supported types: payment_due, payment_overdue, payment_confirmed
    """
    if reminder_type == "payment_due":
        subject = f"Payment due in {payload.get('round_name', 'your round')}"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #ff9800;">Payment Reminder</h2>
                    <p style="color: #666; font-size: 16px;">Hi {user_name},</p>
                    <p style="color: #666; font-size: 16px;">Your payment of <strong>{payload.get('amount', 'N/A')}</strong> is due for <strong>{payload.get('round_name', 'your round')}</strong>.</p>
                    <p style="color: #666;">Due date: <strong>{payload.get('due_date', 'N/A')}</strong></p>
                    <a href="{settings.FRONTEND_URL}" style="display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 20px;">Submit Payment</a>
                </div>
            </body>
        </html>
        """

    elif reminder_type == "payment_overdue":
        subject = f"Payment overdue - {payload.get('round_name', 'your round')}"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #dc3545;">Payment Overdue</h2>
                    <p style="color: #666; font-size: 16px;">Hi {user_name},</p>
                    <p style="color: #666; font-size: 16px;">Your payment of <strong>{payload.get('amount', 'N/A')}</strong> for <strong>{payload.get('round_name', 'your round')}</strong> is now overdue.</p>
                    <p style="color: #dc3545; font-weight: bold;">Please submit your payment immediately to avoid additional penalties.</p>
                    <a href="{settings.FRONTEND_URL}" style="display: inline-block; background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 20px;">Submit Payment Now</a>
                </div>
            </body>
        </html>
        """

    elif reminder_type == "payment_confirmed":
        subject = f"Payment confirmed - {payload.get('round_name', 'your round')}"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #28a745;">Payment Confirmed</h2>
                    <p style="color: #666; font-size: 16px;">Hi {user_name},</p>
                    <p style="color: #666; font-size: 16px;">Your payment of <strong>{payload.get('amount', 'N/A')}</strong> for <strong>{payload.get('round_name', 'your round')}</strong> has been confirmed.</p>
                    <p style="color: #666; margin-top: 20px;">Thank you for staying on track with your commitments!</p>
                </div>
            </body>
        </html>
        """
    else:
        return False

    return await send_email(user_email, user_name, subject, html)
