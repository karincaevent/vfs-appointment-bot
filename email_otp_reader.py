"""
Email OTP Reader
Automatically reads OTP codes from email (IMAP)
"""

import re
import time
import email
from email.header import decode_header
from imapclient import IMAPClient
import logging

logger = logging.getLogger(__name__)


def extract_otp_from_text(text: str) -> str | None:
    """
    Extract OTP code from email body
    
    Common VFS patterns:
    - "Your OTP is: 123456"
    - "OTP: 123456"
    - "Verification code: 123456"
    - "One-time password: 123456"
    """
    # Try multiple OTP patterns
    patterns = [
        r'OTP[:\s]+([0-9]{4,8})',  # OTP: 123456
        r'verification code[:\s]+([0-9]{4,8})',  # verification code: 123456
        r'one-time password[:\s]+([0-9]{4,8})',  # one-time password: 123456
        r'şifre[:\s]+([0-9]{4,8})',  # Turkish: şifre: 123456
        r'\b([0-9]{6})\b',  # Just a 6-digit number (fallback)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def decode_email_text(msg) -> str:
    """Decode email body (handles multipart messages)"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            # Get text content
            if content_type == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode()
                except:
                    pass
    else:
        # Single part message
        try:
            body = msg.get_payload(decode=True).decode()
        except:
            pass
    
    return body


def read_otp_from_email(
    email_address: str,
    email_password: str,
    imap_server: str = "imap.gmail.com",
    imap_port: int = 993,
    timeout_seconds: int = 30,
    from_domain: str = "vfsglobal.com"
) -> str | None:
    """
    Read OTP code from email inbox
    
    Args:
        email_address: Email address (e.g., user@gmail.com)
        email_password: App-specific password (NOT regular password)
        imap_server: IMAP server address
        imap_port: IMAP port (usually 993 for SSL)
        timeout_seconds: How long to wait for email
        from_domain: Filter emails from this domain
    
    Returns:
        OTP code as string, or None if not found
    """
    logger.info(f"📧 Reading OTP from {email_address} (timeout: {timeout_seconds}s)...")
    
    start_time = time.time()
    
    try:
        # Connect to IMAP server
        with IMAPClient(imap_server, port=imap_port, ssl=True) as client:
            logger.info(f"🔌 Connected to {imap_server}")
            
            # Login
            client.login(email_address, email_password)
            logger.info("✅ Logged in successfully")
            
            # Select INBOX
            client.select_folder('INBOX')
            
            # Poll for new emails
            while (time.time() - start_time) < timeout_seconds:
                logger.info(f"🔍 Searching for OTP email from {from_domain}...")
                
                # Search for recent unread emails from VFS
                messages = client.search([
                    'UNSEEN',
                    'FROM', from_domain,
                ])
                
                if messages:
                    logger.info(f"📬 Found {len(messages)} new message(s)")
                    
                    # Get the latest message
                    latest_msg_id = messages[-1]
                    
                    # Fetch email
                    raw_messages = client.fetch([latest_msg_id], ['RFC822'])
                    raw_email = raw_messages[latest_msg_id][b'RFC822']
                    
                    # Parse email
                    msg = email.message_from_bytes(raw_email)
                    
                    # Get subject
                    subject = decode_header(msg['Subject'])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()
                    
                    logger.info(f"📧 Email subject: {subject}")
                    
                    # Get email body
                    body = decode_email_text(msg)
                    
                    # Extract OTP
                    otp = extract_otp_from_text(body)
                    
                    if otp:
                        logger.info(f"✅ OTP found: {otp}")
                        
                        # Mark as read
                        client.add_flags([latest_msg_id], ['\\Seen'])
                        
                        return otp
                    else:
                        logger.warning("⚠️  Email found but no OTP code extracted")
                
                # Wait 2 seconds before next check
                time.sleep(2)
            
            logger.warning(f"⏱️  Timeout ({timeout_seconds}s) - No OTP email received")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error reading email: {e}")
        return None


# Test function
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python email_otp_reader.py <email> <app_password>")
        sys.exit(1)
    
    email_addr = sys.argv[1]
    password = sys.argv[2]
    
    otp = read_otp_from_email(email_addr, password, timeout_seconds=60)
    
    if otp:
        print(f"\n✅ OTP: {otp}")
    else:
        print("\n❌ No OTP found")
