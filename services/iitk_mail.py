"""
IITK Webmail API Service Wrapper.
Provides tools to connect to the IISER/IITK college email systems via IMAP and SMTP.
Supports fetching unread emails, searching the inbox, and sending outgoing mail.
"""
import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import imaplib
import email
import email.header
from datetime import datetime, timedelta

class IITKMail:
    def __init__(self):
        self.email_address = os.environ.get("IITK_EMAIL")
        self.password = os.environ.get("IITK_PASSWORD")
        self.imap_server = os.environ.get("IITK_IMAP_SERVER", "qasid.iitk.ac.in")
        self.smtp_server = os.environ.get("IITK_SMTP_SERVER", "mmtp.iitk.ac.in")
        
        if not self.email_address or not self.password:
            pass # "Warning: IITK_EMAIL or IITK_PASSWORD is not set in environment."

    def _connect(self):
        """Connect and login to IMAP, returns mail object."""
        mail = imaplib.IMAP4_SSL(self.imap_server, 993)
        username = self.email_address.split('@')[0] if '@' in self.email_address else self.email_address
        try:
            mail.login(username, self.password)
        except Exception:
            mail.login(self.email_address, self.password)
        return mail

    def _decode_header(self, header_value):
        """Decode an email header (Subject, From, etc.) into a clean string."""
        if not header_value:
            return "(Unknown)"
        decoded = ""
        for part, encoding in email.header.decode_header(header_value):
            if isinstance(part, bytes):
                decoded += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded += str(part)
        return decoded

    def _get_body(self, msg):
        """Extract plain-text body from an email.message.Message object."""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == 'text/plain':
                    try:
                        return part.get_payload(decode=True).decode(errors='ignore')
                    except Exception:
                        return ""
        else:
            try:
                return msg.get_payload(decode=True).decode(errors='ignore')
            except Exception:
                return ""
        return ""

    def _format_email(self, msg, include_body=True):
        """Format an email.message.Message into a readable string."""
        sender = self._decode_header(msg.get('From'))
        subject = self._decode_header(msg.get('Subject', '(No Subject)'))
        date = msg.get('Date', '(Unknown Date)')
        result = f"From: {sender}\nDate: {date}\nSubject: {subject}"
        if include_body:
            body = self._get_body(msg)
            # Truncate body to avoid flooding
            if body:
                body = body.strip()[:500]
                result += f"\nBody: {body}"
        return result

    def send_mail(self, to_email: str, subject: str, message: str) -> str:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP_SSL(self.smtp_server, 465)
            server.ehlo()
            server.login(self.email_address, self.password)
            server.send_message(msg)
            server.quit()
            return f"Successfully sent email to {to_email}"
        except Exception as e:
            return f"Failed to send email: {e}"

    def unread(self, max_results: int = 5, since_hours: int = 48) -> str:
        """Fetch recent unread emails from the last `since_hours` hours (default 48h)."""
        try:
            mail = self._connect()
            mail.select('inbox')
            
            # Build IMAP search: UNSEEN + received since N hours ago
            since_date = (datetime.now() - timedelta(hours=since_hours)).strftime("%d-%b-%Y")
            status, search_data = mail.search(None, f'(UNSEEN SINCE {since_date})')
            if status != 'OK':
                mail.logout()
                return "Error fetching unread messages."
                
            mail_ids = search_data[0].split()
            
            if not mail_ids:
                mail.logout()
                return "No recent unread emails."
                
            results = []
            count = 0
            for i in reversed(mail_ids):
                if count >= max_results:
                    break
                status, data = mail.fetch(i, '(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        results.append(self._format_email(msg, include_body=True))
                count += 1
            
            mail.logout()
            if not results:
                return "No recent unread emails."
            return "\n---\n".join(results)
        except Exception as e:
            return f"Failed to fetch unread emails: {e}"

    def search(self, query: str, max_results: int = 5, since_days: int = 30) -> str:
        """Search the ENTIRE inbox (read + unread) for emails matching a keyword query.
        
        Uses IMAP SEARCH with BODY/SUBJECT/FROM criteria to find relevant emails.
        Searches within the last `since_days` days (default 30).
        """
        try:
            mail = self._connect()
            mail.select('inbox')
            
            since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
            
            # IMAP OR search: match query in SUBJECT, FROM, or BODY
            # IMAP syntax: (OR (OR (SUBJECT "q") (FROM "q")) (BODY "q"))
            imap_query = f'(OR OR SUBJECT "{query}" FROM "{query}" BODY "{query}" SINCE {since_date})'
            
            status, search_data = mail.search(None, imap_query)
            if status != 'OK':
                mail.logout()
                return f"Error searching inbox for '{query}'."
            
            mail_ids = search_data[0].split()
            
            if not mail_ids:
                mail.logout()
                return f"No emails found matching '{query}'."
            
            results = []
            count = 0
            for i in reversed(mail_ids):
                if count >= max_results:
                    break
                status, data = mail.fetch(i, '(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        results.append(self._format_email(msg, include_body=True))
                count += 1
            
            mail.logout()
            if not results:
                return f"No emails found matching '{query}'."
            return "\n---\n".join(results)
        except Exception as e:
            return f"Failed to search emails: {e}"
