#!/usr/bin/env python3
"""
SMTP Connectivity Test Script

Tests SMTP server connectivity and configuration to diagnose email sending issues.
"""

import os
import smtplib
import sys

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


def test_smtp_connection():
    """Test SMTP server connectivity and authentication."""

    # Get SMTP configuration
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@selfmemory.com")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    print("=" * 80)
    print("SMTP Configuration Test")
    print("=" * 80)
    print(f"SMTP_HOST: {smtp_host}")
    print(f"SMTP_PORT: {smtp_port}")
    print(f"SMTP_USERNAME: {smtp_username}")
    print(f"SMTP_PASSWORD: {'*' * len(smtp_password) if smtp_password else 'Not set'}")
    print(f"SMTP_FROM_EMAIL: {smtp_from_email}")
    print(f"SMTP_USE_TLS: {smtp_use_tls}")
    print("=" * 80)

    if not smtp_host:
        print("❌ ERROR: SMTP_HOST is not configured")
        return False

    if not smtp_username or not smtp_password:
        print("❌ ERROR: SMTP credentials not configured")
        return False

    # Test connection
    print(f"\n🔍 Testing connection to {smtp_host}:{smtp_port}...")

    try:
        if smtp_port == 465:
            print("📧 Using SMTP_SSL (port 465)...")
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            print("✅ SSL connection established")
        else:
            print(
                f"📧 Using SMTP with {'STARTTLS' if smtp_use_tls else 'no encryption'} (port {smtp_port})..."
            )
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            print("✅ Connection established")

            if smtp_use_tls:
                print("🔒 Starting TLS...")
                server.starttls()
                print("✅ TLS connection established")

        # Test authentication
        print(f"\n🔐 Testing authentication with {smtp_username}...")
        server.login(smtp_username, smtp_password)
        print("✅ Authentication successful")

        server.quit()
        print("\n✅ All SMTP tests passed!")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\n💡 Solutions:")
        print("  1. Verify SMTP_USERNAME and SMTP_PASSWORD are correct")
        print("  2. Check if the email account requires app-specific passwords")
        return False

    except (OSError, ConnectionRefusedError, TimeoutError) as e:
        print(f"\n❌ Connection failed: {type(e).__name__}: {e}")
        print("\n💡 Solutions:")
        print(f"  1. Verify '{smtp_host}' is accessible from your network")
        print("  2. Check if firewall is blocking the connection")
        print("  3. Try using a different SMTP server (Gmail, SendGrid, etc.)")
        print("  4. For development, consider using a local SMTP server like MailHog")
        return False

    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
        return False


def print_alternative_smtp_configs():
    """Print example configurations for popular SMTP services."""
    print("\n" + "=" * 80)
    print("Alternative SMTP Configuration Examples")
    print("=" * 80)

    print("\n📮 Gmail (App Password required):")
    print("SMTP_HOST=smtp.gmail.com")
    print("SMTP_PORT=587")
    print("SMTP_USERNAME=your-email@gmail.com")
    print("SMTP_PASSWORD=your-app-password")
    print("SMTP_USE_TLS=true")

    print("\n📮 SendGrid:")
    print("SMTP_HOST=smtp.sendgrid.net")
    print("SMTP_PORT=587")
    print("SMTP_USERNAME=apikey")
    print("SMTP_PASSWORD=your-sendgrid-api-key")
    print("SMTP_USE_TLS=true")

    print("\n📮 Mailgun:")
    print("SMTP_HOST=smtp.mailgun.org")
    print("SMTP_PORT=587")
    print("SMTP_USERNAME=postmaster@your-domain.mailgun.org")
    print("SMTP_PASSWORD=your-mailgun-password")
    print("SMTP_USE_TLS=true")

    print("\n📮 Local Development (MailHog):")
    print("SMTP_HOST=localhost")
    print("SMTP_PORT=1025")
    print("SMTP_USERNAME=")  # Leave empty
    print("SMTP_PASSWORD=")  # Leave empty
    print("SMTP_USE_TLS=false")
    print("\nInstall MailHog: https://github.com/mailhog/MailHog")
    print("Run: mailhog (Web UI at http://localhost:8025)")

    print("\n📮 Disable Email (Development Mode):")
    print("# Leave SMTP_HOST empty or comment it out")
    print("# SMTP_HOST=")
    print("\nEmails will be logged to console instead of sent")
    print("=" * 80)


if __name__ == "__main__":
    success = test_smtp_connection()

    if not success:
        print_alternative_smtp_configs()
        sys.exit(1)

    sys.exit(0)
