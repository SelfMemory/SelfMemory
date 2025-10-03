#!/usr/bin/env python3
"""
SMTP Connection Test Script

Tests the SMTP configuration from .env and provides detailed diagnostic information.
"""

import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load environment variables from .env
from dotenv import load_dotenv

load_dotenv()

# SMTP Configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "mail.selfmemory.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "no-reply@selfmemory.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "no-reply@selfmemory.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"

print("=" * 60)
print("SMTP Connection Test")
print("=" * 60)
print(f"Host: {SMTP_HOST}")
print(f"Port: {SMTP_PORT}")
print(f"Username: {SMTP_USERNAME}")
print(f"From Email: {SMTP_FROM_EMAIL}")
print(f"Password: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else '(NOT SET)'}")
print("=" * 60)

# Test 1: Basic network connectivity
print("\n[TEST 1] Testing basic network connectivity...")
try:
    sock = socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=10)
    sock.close()
    print("✅ Network connection successful")
except TimeoutError:
    print("❌ Connection timed out - Server not reachable or firewall blocking")
    exit(1)
except socket.gaierror as e:
    print(f"❌ DNS resolution failed: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Connection failed: {type(e).__name__}: {e}")
    exit(1)


# Test 2: SMTP connection (SSL or TLS)
print("\n[TEST 2] Testing SMTP connection (SSL/TLS)...")
try:
    if SMTP_USE_TLS:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        print("✅ SMTP connection established (plain)")
        print("[TEST 2a] Starting TLS...")
        server.ehlo()
        server.starttls()
        print("✅ TLS started successfully")
    else:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        print("✅ SMTP SSL connection established")

    # Test 3: SMTP greeting
    print("\n[TEST 3] Testing SMTP greeting...")
    response = server.ehlo()
    print(f"✅ Server greeting: {response}")

    # Test 4: Authentication
    print("\n[TEST 4] Testing authentication...")
    if not SMTP_PASSWORD:
        print("❌ Password not set in environment")
        server.quit()
        exit(1)

    try:
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        print("✅ Authentication successful")
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        server.quit()
        exit(1)

    # Test 5: Send test email
    print("\n[TEST 5] Sending test email...")
    test_email = input(
        "Enter email address to send test to (or press Enter to skip): "
    ).strip()

    if test_email:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = test_email
        msg["Subject"] = "SMTP Test from SelfMemory"

        body = """
This is a test email from the SelfMemory SMTP configuration test.

If you received this, your SMTP configuration is working correctly!
"""
        msg.attach(MIMEText(body, "plain"))

        try:
            server.send_message(msg)
            print(f"✅ Test email sent successfully to {test_email}")
        except Exception as e:
            print(f"❌ Failed to send test email: {type(e).__name__}: {e}")
    else:
        print("⏭️  Skipping test email send")

    server.quit()
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - SMTP is configured correctly!")
    print("=" * 60)

except smtplib.SMTPException as e:
    print(f"❌ SMTP error: {type(e).__name__}: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {type(e).__name__}: {e}")
    exit(1)
