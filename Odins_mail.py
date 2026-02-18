# odin_mail.py
# Odin Mail v0.1 – Temporal Email Client with Polling
# Uses Odin's Eye as dependency
# MIT License – free for all

import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import threading
from odins_eye import OdinsEye

# ────────────────────────────────────────────────
# Global Defaults
# ────────────────────────────────────────────────

GLOBAL_ROOT = 50000
SEARCH_RANGE_SIZE = 1_000_000
MAGIC_PREFIX = "AB42"
POLL_INTERVAL_SEC = 60
POLL_BATCH_SIZE = 100  # masks per poll cycle
MAX_TEXT_LENGTH = 64 * 1024

# ────────────────────────────────────────────────
# User State
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []
        self.sent: List[Dict] = []
        self.queue: List[Dict] = []
        self.search_start = self._hash_to_start(username)
        self.last_checked_mask = self.search_start
        self.polling = False

    def _hash_to_start(self, username: str) -> int:
        h = hashlib.sha256(username.encode()).hexdigest()
        return GLOBAL_ROOT + int(h[:8], 16) % SEARCH_RANGE_SIZE

    def save(self, path: str = "odin_state.json"):
        state = {
            "username": self.username,
            "inbox": self.inbox,
            "sent": self.sent,
            "queue": self.queue,
            "search_start": self.search_start,
            "last_checked_mask": self.last_checked_mask
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
            user.last_checked_mask = state.get("last_checked_mask", user.search_start)
            return user
        except FileNotFoundError:
            username = input("Enter username (e.g. bubba): ").strip()
            return cls(username)


# ────────────────────────────────────────────────
# Message & Polling
# ────────────────────────────────────────────────

def create_message(to: str, subject: str, body: str, from_user: str, delivery_date: Optional[str] = None, attachment_coord: Optional[Dict] = None) -> Dict:
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


def poll_inbox(user: UserState, eye: OdinsEye):
    print(f"Polling {user.username}@odin range: {user.last_checked_mask} → {user.search_start + SEARCH_RANGE_SIZE}")

    current = user.last_checked_mask
    end = user.search_start + SEARCH_RANGE_SIZE

    while current < end:
        # Try decode with reasonable length guess (for v0.1, fixed 1024 bytes)
        try:
            coord = {
                "start_mask": user.search_start,
                "end_mask": current,
                "anchor_mask": current - 8,  # rough
                "last_choice": 0,  # placeholder
                "last_direction": 1,
                "length_bytes": 1024
            }
            data = eye.decode(coord)
            msg_str = data.decode('utf-8', errors='ignore')
            if msg_str.startswith(MAGIC_PREFIX + user.username):
                # Valid message
                msg = json.loads(msg_str[len(MAGIC_PREFIX + user.username):])
                if msg["to"] == user.username:
                    if msg["delivery_date"] and msg["delivery_date"] > datetime.now().isoformat():
                        user.queue.append({"msg": msg, "coord": coord})
                    else:
                        user.inbox.append({"msg": msg, "coord": coord})
                    print(f"Found message from {msg['from']}: {msg['subject']}")
        except Exception:
            pass  # skip invalid

        current += 1  # step by 1 for v0.1 – can batch later

    user.last_checked_mask = current
    user.save()


def start_polling(user: UserState, eye: OdinsEye):
    if user.polling:
        return
    user.polling = True

    def poll_loop():
        while user.polling:
            poll_inbox(user, eye)
            time.sleep(POLL_INTERVAL_SEC)

    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()
    print("Polling started in background")


# ────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────

def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.search_start)

    print(f"Odin Mail v0.1 – Welcome, {user.username}@odin")

    start_polling(user, eye)  # auto-start background polling

    while True:
        print("\nCommands: compose | inbox | queue | poll | save | exit")
        cmd = input("> ").strip().lower()

        if cmd == "exit":
            user.polling = False
            user.save()
            print("Goodbye.")
            break

        elif cmd == "compose":
            to = input("To: ")
            subject = input("Subject: ")
            body = input("Body:\n")
            delivery = input("Delivery date (YYYY-MM-DD) or blank: ").strip() or None
            attach = input("Attachment coord JSON (optional): ").strip() or None
            attach_coord = json.loads(attach) if attach else None

            msg = create_message(to, subject, body, user.username, delivery, attach_coord)
            send_message(user, eye, msg)

        elif cmd == "inbox":
            show_inbox(user)

        elif cmd == "queue":
            print("\nQueued:")
            for i, item in enumerate(user.queue):
                msg = item["msg"]
                print(f"[{i+1}] To: {msg['to']} | Subject: {msg['subject']} | Delivery: {msg['delivery_date']}")

        elif cmd == "poll":
            poll_inbox(user, eye)

        elif cmd == "save":
            user.save()
            print("State saved.")

        else:
            print("Unknown command.")

if __name__ == '__main__':
    main()