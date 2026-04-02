"""
Gmail API Service Wrapper.
Allows for searching the Gmail inbox (with semantic RAG), fetching unread emails,
and sending outgoing plaintext emails.
"""
import sys
import base64
from googleapiclient.discovery import build
from tqdm import tqdm
from langchain.schema import Document
from RAG import RAG
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_message_body(msg):
    payload = msg.get("payload", {})
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8")
    else:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")
    return None


class Gmail:
    def __init__(self, credentials):
        try:
            self.service = build("gmail", "v1", credentials=credentials)
        except:
            self.service = None
            pass # "Unable to make connection with Gmail")



    def search(self, query: str, results: int = 5, rag: bool = False):
        try:
            pass # "Searching for Mails", end="\r", flush=True)
            results = (
                self.service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX"], maxResults=results, q=query)
                .execute()
            )
            messages = results.get("messages", [])

            if not messages:
                return "No messages found."
            
            pass # "Fetching Complete Messages...", end="\r", flush=True)
            detailed_messages = []
            docs = []
            for m in tqdm(messages):
                msg_id = m["id"]
                msg_detail = self.service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()
                payload = msg_detail.get("payload", {})
                headers = payload.get("headers", [])
                body = get_message_body(msg_detail)

                details = {h["name"]: h["value"] for h in headers}
                msg = {
                    "id": msg_id,
                    "from": details.get("From"),
                    "subject": details.get("Subject"),
                    "date": details.get("Date"),
                    "body": body,
                }
                detailed_messages.append(msg)

                # Convert to Document for RAG
                content = f"From: {msg['from']}\nSubject: {msg['subject']}\nDate: {msg['date']}\nBody: {msg['body']}"
                docs.append(Document(page_content=content, metadata={"id": msg_id}))

            if rag:  # If rag=True, run semantic retrieval
                return RAG(docs, query, results=results)
            else:
                return detailed_messages

        except Exception as error:
            return f"Error: {error}"
        
    def send_mail(self, to: str, subject: str, body: str, cc: list = None, bcc: list = None, is_html: bool = False):
        """
        Send an email using Gmail API.
        """
        try:
            if not self.service:
                return "Gmail service not initialized."

            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject

            if cc:
                message["cc"] = ", ".join(cc)
            if bcc:
                message["bcc"] = ", ".join(bcc)

            if is_html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            sent_message = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            return f"Message sent! ID: {sent_message['id']}"

        except Exception as error:
            return f"Error sending email: {error}"
        


    def unread(self, max_results: int = 10, rag: bool = False, query: str = None):
        """
        Fetch unread mails from inbox.
        If query is provided, apply Gmail's native query search on unread mails.
        If rag=True, return semantic search using RAG on unread mails.
        """
        try:
            if not self.service:
                return "Gmail service not initialized."

            pass # "Fetching unread emails...", end="\r")

            search_query = "is:unread"
            if query:
                search_query += f" {query}"

            results = (
                self.service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX"], q=search_query, maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])

            if not messages:
                return "No unread messages found."

            detailed_messages = []
            docs = []
            for m in messages:
                msg_id = m["id"]
                msg_detail = self.service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()

                payload = msg_detail.get("payload", {})
                headers = payload.get("headers", [])
                body = get_message_body(msg_detail)

                details = {h["name"]: h["value"] for h in headers}
                msg = {
                    "id": msg_id,
                    "from": details.get("From"),
                    "subject": details.get("Subject"),
                    "date": details.get("Date"),
                    "body": body,
                }
                detailed_messages.append(msg)

                # Prepare docs for RAG
                content = f"From: {msg['from']}\nSubject: {msg['subject']}\nDate: {msg['date']}\nBody: {msg['body']}"
                docs.append(Document(page_content=content, metadata={"id": msg_id}))

            if rag:
                return RAG(docs, query or "Unread emails")
            else:
                return detailed_messages

        except Exception as error:
            return f"Error fetching unread emails: {error}"
