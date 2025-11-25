#!/usr/bin/env python3
"""
Send Test Email Script

Sends an actual test email using your SMTP configuration to verify everything works.
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def send_test_email(recipient_email: str):
    """Send a test email to the specified recipient."""

    # Get SMTP configuration
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@selfmemory.com")
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "SelfMemory")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    smtp_timeout = int(os.getenv("SMTP_TIMEOUT", "10"))

    print("=" * 80)
    print("SENDING TEST EMAIL")
    print("=" * 80)
    print(f"From: {smtp_from_name} <{smtp_from_email}>")
    print(f"To: {recipient_email}")
    print(f"Server: {smtp_host}:{smtp_port}")
    print(f"Timeout: {smtp_timeout}s")
    print("=" * 80)

    if not smtp_host or not smtp_username or not smtp_password:
        print("\n❌ ERROR: SMTP not configured")
        print("Please check your .env file")
        return False

    # Create email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🧪 SelfMemory Test Email"
    msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
    msg["To"] = recipient_email

    # Plain text version
    text_body = (
        """
Hello!

This is a test email from your SelfMemory installation.

If you're reading this, your SMTP configuration is working correctly! ✅

Test Details:
- SMTP Host: """
        + smtp_host
        + """
- SMTP Port: """
        + str(smtp_port)
        + """
- Timeout: """
        + str(smtp_timeout)
        + """s
- Configuration: Working perfectly!

Next steps:
1. Try sending an invitation email through your dashboard
2. All invitation emails should now work without timeout errors

Best regards,
The SelfMemory System
"""
    )

    # HTML version
    html_body = (
        """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background-color: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }
        .success-box { background-color: #d1fae5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .info-box { background-color: #e0e7ff; border-left: 4px solid #6366f1; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 30px; }
        h1 { margin: 0; font-size: 28px; }
        .emoji { font-size: 48px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="emoji">🧪</div>
            <h1>SelfMemory Test Email</h1>
        </div>
        <div class="content">
            <p>Hello!</p>

            <div class="success-box">
                <strong>✅ Success!</strong> Your SMTP configuration is working correctly!
            </div>

            <p>If you're reading this email, it means:</p>
            <ul>
                <li>✅ DNS resolution is working</li>
                <li>✅ SMTP server is accessible</li>
                <li>✅ SSL/TLS connection is established</li>
                <li>✅ Authentication is successful</li>
                <li>✅ Email delivery is working</li>
            </ul>

            <div class="info-box">
                <strong>Configuration Details:</strong><br>
                • SMTP Host: """
        + smtp_host
        + """<br>
                • SMTP Port: """
        + str(smtp_port)
        + """<br>
                • Timeout: """
        + str(smtp_timeout)
        + """s<br>
                • Status: <strong>Working perfectly!</strong>
            </div>

            <p><strong>Next Steps:</strong></p>
            <ol>
                <li>Try sending an invitation email through your dashboard</li>
                <li>All invitation emails should now work without timeout errors</li>
                <li>Monitor your logs for any issues</li>
            </ol>

            <p>Need help? Check the documentation files in your selfmemory-core directory.</p>
        </div>
        <div class="footer">
            <p>This is an automated test message from SelfMemory</p>
        </div>
    </div>
</body>
</html>
"""
    )

    # Attach both versions
    part1 = MIMEText(text_body, "plain")
    part2 = MIMEText(html_body, "html")
    msg.attach(part1)
    msg.attach(part2)

    # Send email
    print("\n📧 Connecting to SMTP server...")
    try:
        if smtp_port == 465:
            print(f"🔒 Using SMTP_SSL (port 465) with {smtp_timeout}s timeout...")
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                print("✅ SSL connection established")
                print(f"🔐 Authenticating as {smtp_username}...")
                server.login(smtp_username, smtp_password)
                print("✅ Authentication successful")
                print(f"📮 Sending email to {recipient_email}...")
                server.send_message(msg)
                print("✅ Email sent successfully!")
        else:
            print(f"📧 Using SMTP (port {smtp_port}) with {smtp_timeout}s timeout...")
            with smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                print("✅ Connection established")
                if smtp_use_tls:
                    print("🔒 Starting TLS...")
                    server.starttls()
                    print("✅ TLS established")
                print(f"🔐 Authenticating as {smtp_username}...")
                server.login(smtp_username, smtp_password)
                print("✅ Authentication successful")
                print(f"📮 Sending email to {recipient_email}...")
                server.send_message(msg)
                print("✅ Email sent successfully!")

        print("\n" + "=" * 80)
        print("✅ TEST PASSED - Check your inbox!")
        print("=" * 80)
        print(f"\n📬 An email should arrive at: {recipient_email}")
        print("   Check spam folder if you don't see it in a few minutes.")
        print("\n💡 Your SMTP configuration is now confirmed working!")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\n💡 Solutions:")
        print("  1. Verify SMTP_USERNAME and SMTP_PASSWORD in .env")
        print("  2. Check if the email account requires app-specific passwords")
        return False

    except TimeoutError as e:
        print(f"\n❌ Connection timeout: {e}")
        print("\n💡 Solutions:")
        print(f"  1. Current timeout: {smtp_timeout}s - may need to increase")
        print("  2. Check if firewall is blocking the connection")
        print("  3. Verify mail server is accessible from your network")
        return False

    except Exception as e:
        print(f"\n❌ Error sending email: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_test_email.py <recipient_email>")
        print("\nExample:")
        print("  python3 send_test_email.py your-email@gmail.com")
        sys.exit(1)

    recipient = sys.argv[1]

    # Validate email format (basic)
    if "@" not in recipient or "." not in recipient.split("@")[1]:
        print(f"❌ Invalid email address: {recipient}")
        sys.exit(1)

    success = send_test_email(recipient)
    sys.exit(0 if success else 1)
