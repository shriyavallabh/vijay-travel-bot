#!/usr/bin/env python3
"""
Manual Trigger Script for Morning Concierge
Sends WhatsApp Template Messages to active travelers with their daily plan

Usage:
    python manual_trigger.py

This script:
1. Calculates current trip day based on start date (Dec 9, 2024)
2. Sends template message "trip_morning_nudge" to test users
3. Template includes button with payload: GET_PLAN_DAY_{day_number}
"""
import os
import hmac
import hashlib
import requests
from datetime import datetime, date
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")

# Test Users Configuration
TEST_USERS = [
    {
        "phone": "919075910505",
        "name": "Test User A",
        "start_date": date(2024, 12, 9)
    },
    {
        "phone": "919850740750",
        "name": "Test User B",
        "start_date": date(2024, 12, 9)
    }
]

# Template Configuration
TEMPLATE_NAME = "trip_morning_nudge"
TEMPLATE_LANGUAGE = "en"


def generate_appsecret_proof(access_token: str, app_secret: str) -> str:
    """Generate appsecret_proof for Meta API authentication"""
    return hmac.new(
        app_secret.encode('utf-8'),
        access_token.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def calculate_trip_day(start_date: date) -> int:
    """
    Calculate the current day of the trip.

    Args:
        start_date: Trip start date

    Returns:
        Day number (1-8), or 0 if trip hasn't started, or -1 if completed
    """
    today = date.today()

    if today < start_date:
        return 0  # Trip hasn't started

    delta = (today - start_date).days + 1  # Day 1 is the first day

    if delta > 8:
        return -1  # Trip completed

    return delta


def send_template_message(phone: str, customer_name: str, day_number: int) -> bool:
    """
    Send WhatsApp template message with morning nudge.

    Args:
        phone: Phone number (with country code, no +)
        customer_name: Customer's name for personalization
        day_number: Current day of the trip

    Returns:
        True if successful, False otherwise
    """
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    # Generate appsecret_proof
    proof = generate_appsecret_proof(WHATSAPP_ACCESS_TOKEN, FB_APP_SECRET)

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Template message payload
    # Template variables: {{1}} = customer name, {{2}} = day number
    # Button payload: GET_PLAN_DAY_{day_number}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {
                "code": TEMPLATE_LANGUAGE
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": customer_name
                        },
                        {
                            "type": "text",
                            "text": str(day_number)
                        }
                    ]
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "payload",
                            "payload": f"GET_PLAN_DAY_{day_number}"
                        }
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(
            f"{url}?appsecret_proof={proof}",
            json=payload,
            headers=headers
        )

        if response.status_code == 200:
            print(f"[Trigger] Successfully sent morning nudge to {phone}")
            return True
        else:
            print(f"[Trigger] Error sending to {phone}: {response.status_code}")
            print(f"[Trigger] Response: {response.text}")
            return False

    except Exception as e:
        print(f"[Trigger] Exception sending to {phone}: {e}")
        return False


def send_text_fallback(phone: str, customer_name: str, day_number: int) -> bool:
    """
    Fallback: Send regular text message if template fails or isn't set up.
    This is useful for testing before the template is approved.

    Args:
        phone: Phone number
        customer_name: Customer's name
        day_number: Current day of the trip

    Returns:
        True if successful
    """
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    proof = generate_appsecret_proof(WHATSAPP_ACCESS_TOKEN, FB_APP_SECRET)

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Compose morning message
    message = f"""Good Morning, {customer_name}! ☀️

Today is Day {day_number} of your Rajasthan Royal Heritage Tour!

Ready to explore? Reply with:
• "Day {day_number} plan" - Get your detailed itinerary
• "Videos" - Get video guides for today's attractions
• "Driver" - Get your driver's contact details

Have a wonderful day! 🏰"""

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }

    try:
        response = requests.post(
            f"{url}?appsecret_proof={proof}",
            json=payload,
            headers=headers
        )

        if response.status_code == 200:
            print(f"[Trigger] Successfully sent text message to {phone}")
            return True
        else:
            print(f"[Trigger] Error sending text to {phone}: {response.status_code}")
            print(f"[Trigger] Response: {response.text}")
            return False

    except Exception as e:
        print(f"[Trigger] Exception: {e}")
        return False


def main():
    """Main function to trigger morning concierge messages"""
    print("\n" + "="*60)
    print("MORNING CONCIERGE - MANUAL TRIGGER")
    print("="*60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Template: {TEMPLATE_NAME}")
    print("="*60 + "\n")

    # Validate configuration
    if not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
        print("[ERROR] WhatsApp credentials not configured in .env")
        print("Required: WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN, FB_APP_SECRET")
        return

    success_count = 0
    fail_count = 0

    for user in TEST_USERS:
        phone = user["phone"]
        name = user["name"]
        start_date = user["start_date"]

        # Calculate current trip day
        day_number = calculate_trip_day(start_date)

        print(f"\n[Trigger] Processing {name} ({phone})")
        print(f"[Trigger] Trip Start: {start_date}")
        print(f"[Trigger] Current Day: {day_number}")

        if day_number == 0:
            print(f"[Trigger] Skipping - Trip hasn't started yet")
            continue
        elif day_number == -1:
            print(f"[Trigger] Skipping - Trip already completed")
            continue

        # Send morning nudge
        print(f"[Trigger] Sending Morning Nudge to {phone}...")
        print(f"[Trigger] Button Payload: GET_PLAN_DAY_{day_number}")

        # Try template first, fall back to text message
        success = send_template_message(phone, name, day_number)

        if not success:
            print(f"[Trigger] Template failed, trying text fallback...")
            success = send_text_fallback(phone, name, day_number)

        if success:
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "="*60)
    print("TRIGGER COMPLETE")
    print("="*60)
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
