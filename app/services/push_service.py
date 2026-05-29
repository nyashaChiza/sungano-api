import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings


async def send_push_notification(
    expo_tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send push notification via Expo Push Service
    """
    if not expo_tokens:
        return True

    url = "https://exp.host/--/api/v2/push/send"

    # Build notification payload
    messages = []
    for token in expo_tokens:
        message = {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "badge": 1,
        }
        if data:
            message["data"] = data
        messages.append(message)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=messages)
        return response.status_code == 200
    except Exception as e:
        print(f"Push notification send failed: {e}")
        return False


async def send_payment_due_notification(
    expo_tokens: List[str],
    round_name: str,
    amount: str,
    due_date: str,
) -> bool:
    """
    Notify about upcoming payment
    """
    return await send_push_notification(
        expo_tokens,
        title="Payment Due",
        body=f"{amount} payment due for {round_name}",
        data={
            "type": "payment_due",
            "round_name": round_name,
            "amount": amount,
            "due_date": due_date,
        },
    )


async def send_payment_submitted_notification(
    expo_tokens: List[str],
    payer_name: str,
    round_name: str,
    amount: str,
) -> bool:
    """
    Notify recipient of payment submission
    """
    return await send_push_notification(
        expo_tokens,
        title="Payment Submitted",
        body=f"{payer_name} submitted {amount} for {round_name}",
        data={
            "type": "payment_submitted",
            "payer_name": payer_name,
            "round_name": round_name,
            "amount": amount,
        },
    )


async def send_payment_confirmed_notification(
    expo_tokens: List[str],
    round_name: str,
    amount: str,
) -> bool:
    """
    Notify about payment confirmation
    """
    return await send_push_notification(
        expo_tokens,
        title="Payment Confirmed",
        body=f"Your {amount} payment was confirmed for {round_name}",
        data={
            "type": "payment_confirmed",
            "round_name": round_name,
            "amount": amount,
        },
    )


async def send_default_notice_notification(
    expo_tokens: List[str],
    round_name: str,
    amount: str,
) -> bool:
    """
    Notify about payment default
    """
    return await send_push_notification(
        expo_tokens,
        title="Payment Default",
        body=f"Your {amount} payment is overdue for {round_name}",
        data={
            "type": "default_notice",
            "round_name": round_name,
            "amount": amount,
        },
    )


async def send_round_invitation_notification(
    expo_tokens: List[str],
    inviter_name: str,
    round_name: str,
) -> bool:
    """
    Notify about round invitation
    """
    return await send_push_notification(
        expo_tokens,
        title="Round Invitation",
        body=f"{inviter_name} invited you to {round_name}",
        data={
            "type": "round_invitation",
            "inviter_name": inviter_name,
            "round_name": round_name,
        },
    )


async def send_goal_invitation_notification(
    expo_tokens: List[str],
    inviter_name: str,
    goal_name: str,
) -> bool:
    """
    Notify about goal invitation
    """
    return await send_push_notification(
        expo_tokens,
        title="Goal Invitation",
        body=f"{inviter_name} invited you to {goal_name}",
        data={
            "type": "goal_invitation",
            "inviter_name": inviter_name,
            "goal_name": goal_name,
        },
    )
