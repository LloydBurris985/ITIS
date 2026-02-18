# odin_mail.py
# Odin Mail v0.1 – Temporal Email Client for the Odin Project / ITIS
# Uses Odin's Eye as dependency
# MIT License – free for all

import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from odins_eye import OdinsEye  # our core oscillator

# ────────────────────────────────────────────────
# Global Defaults (agreed rules for all users)
# ────────────────────────────────────────────────

GLOBAL_ROOT = 50000
SEARCH_RANGE_SIZE = 1_000_000  # masks to search
MAGIC_PREFIX = "AB42"
POLL_INTERVAL_SEC = 60
MAX_TEXT_LENGTH = 64 * 1024  # 64 KB

# ────────────────────────────────────────────────
# User State (saved in ~/.odin_mail.json or similar)
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []          # received messages
        self.sent: List[Dict] = []           # sent messages
        self.queue: List[Dict] = []          # future-delivery messages
        self.search_start = self._hash_to_start(username)

    def _hash_to_start(self, username: str) -> int:
        """Auto-generate default search start from username"""
        h = hashlib.sha256(username.encode()).hexdigest()
        return GLOBAL_ROOT + int(h[:8], 16) % SEARCH_RANGE_SIZE

    def save(self, path: str = "odin_state.json"):
        state = {
            "username": self.username,
            "inbox": self.inbox,
            "sent": self.sent,
            "queue": self.queue,
            "search_start": self.search_start
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    @classmethod
    def load(cls, path: str = "odin_state.json") -> "UserState":
        try:
            with open(path) as f:
                state = json.load(f)
            user = cls(state["username"])
            user.inbox = state.get("inbox", [])
            user.sent = state.get("sent", [])
            user.queue = state.get("queue", [])
            user.search_start = state.get("search_start", user._hash_to_start(state["username"]))
            return user
        except FileNotFoundError:
            username = input("Enter username (e.g. bubba): ").strip()
            return cls(username)


# ────────────────────────────────────────────────
# Message Structure
# ────────────────────────────────────────────────

def create_message(
    to: str,
    subject: str,
    body: str,
    from_user: str,
    delivery_date: Optional[str] = None,
    attachment_coord: Optional[Dict] = None
) -> Dict:
    msg = {
        "from": from_user,
        "to": to,
        "subject": subject,
        "body": body[:MAX_TEXT_LENGTH],
        "sent_date": datetime.now().isoformat(),
        "delivery_date": delivery_date,
        "attachment": attachment_coord,
        "status": "queued" if delivery_date else "sent"
    }
    return msg


# ────────────────────────────────────────────────
# Odin Mail Core Functions
# ────────────────────────────────────────────────

def send_message(user: UserState, eye: OdinsEye, msg: Dict):
    # Encode message as JSON → bytes
    msg_bytes = json.dumps(msg).encode()

    # Encode into lattice
    coord = eye.encode(msg_bytes)

    # For now, "send" means save to sent/queue
    if msg["delivery_date"]:
        user.queue.append({"msg": msg, "coord": coord})
        print(f"Message queued for delivery on {msg['delivery_date']}")
    else:
        user.sent.append({"msg": msg, "coord": coord})
        print("Message sent (dropped into lattice)")

    user.save()


def poll_inbox(user: UserState, eye: OdinsEye):
    now = datetime.now().isoformat()

    # Check queued messages
    delivered = []
    for item in user.queue[:]:
        if item["msg"]["delivery_date"] <= now:
            user.inbox.append(item)
            delivered.append(item)
            user.queue.remove(item)

    if delivered:
        print(f"Delivered {len(delivered)} queued messages to inbox")

    # Future: real lattice search here (search range for messages with magic prefix + username hash)
    # For v0.1, we simulate with queue only
    print("Inbox polled. New messages:", len(user.inbox))


def show_inbox(user: UserState):
    print("\nInbox:")
    for i, item in enumerate(user.inbox):
        msg = item["msg"]
        print(f"[{i+1}] From: {msg['from']} | Subject: {msg['subject']}")
        print(f"   Sent: {msg['sent_date']}")
        if msg.get("delivery_date"):
            print(f"   Delivered: {msg['delivery_date']}")
        print(f"   Body preview: {msg['body'][:100]}...")
        if msg.get("attachment"):
            print(f"   Attachment coord: {msg['attachment']}")
        print("-" * 60)


def compose_message(user: UserState):
    to = input("To: ")
    subject = input("Subject: ")
    body = input("Body (multi-line ok, Ctrl+D or Ctrl+Z to end):\n")
    delivery = input("Delivery date (YYYY-MM-DD) or leave blank: ").strip() or None
    attach = input("Attachment coord JSON (optional, paste or blank): ").strip() or None

    attach_coord = json.loads(attach) if attach else None

    msg = create_message(
        to=to,
        subject=subject,
        body=body,
        from_user=user.username,
        delivery_date=delivery,
        attachment_coord=attach_coord
    )

    return msg


# ────────────────────────────────────────────────
# CLI Entry Point
# ────────────────────────────────────────────────

def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.search_start)

    print(f"Odin Mail v0.1 – Welcome, {user.username}@odin")

    while True:
        print("\nCommands: compose | inbox | send | queue | poll | save | exit")
        cmd = input("> ").strip().lower()

        if cmd == "exit":
            user.save()
            print("Goodbye.")
            break

        elif cmd == "compose":
            msg = compose_message(user)
            send_message(user, eye, msg)

        elif cmd == "inbox":
            show_inbox(user)

        elif cmd == "queue":
            print("\nQueued messages:")
            for i, item in enumerate(user.queue):
                msg = item["msg"]
                print(f"[{i+1}] To: {msg['to']} | Subject: {msg['subject']}")
                print(f"   Delivery: {msg['delivery_date']}")

        elif cmd == "send":
            print("Sending queued messages... (simulated)")
            for item in user.queue[:]:
                send_message(user, eye, item["msg"])
            user.queue = []

        elif cmd == "poll":
            poll_inbox(user, eye)

        elif cmd == "save":
            user.save()
            print("State saved.")

        else:
            print("Unknown command.")


if __name__ == '__main__':
    main()