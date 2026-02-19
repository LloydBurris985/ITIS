# odin_mail.py
# Odin Mail v0.1 – Temporal Email Client with Runway-Based Polling
# Uses Odin's Eye as dependency
# MIT License – free for all

import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import threading
from odins_eye import OdinsEye  # must be in same folder

# ────────────────────────────────────────────────
# Global Defaults – Pre-agreed for all users
# ────────────────────────────────────────────────

GLOBAL_ROOT = 50000                  # agreed runway start (root)
RUNWAY_END = 60000                   # agreed runway end – messages cannot pass this
SEARCH_RANGE_SIZE = RUNWAY_END - GLOBAL_ROOT
MAGIC_PREFIX = "AB42"                # message must start with this + username[:4]
POLL_INTERVAL_SEC = 60               # how often to poll
POLL_BATCH_SIZE = 200                # masks checked per cycle
POLL_STEP_SIZE = 5                   # step this many masks (speed vs thoroughness)
POLL_THROTTLE_SEC = 0.2              # sleep between decode attempts (~5/sec max)
LENGTH_GUESSES = [512, 1024, 2048, 4096]  # try these lengths
MAX_TEXT_LENGTH = 64 * 1024          # text body limit

# ────────────────────────────────────────────────
# User State (saved/loaded from JSON)
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []          # delivered messages
        self.sent: List[Dict] = []           # sent messages
        self.queue: List[Dict] = []          # future-delivery messages
        self.last_checked_mask = GLOBAL_ROOT  # resume point in runway
        self.polling = False

    def save(self, path: str = "odin_state.json"):
        state = {
            "username": self.username,
            "inbox": self.inbox,
            "sent": self.sent,
            "queue": self.queue,
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
            user.last_checked_mask = state.get("last_checked_mask", GLOBAL_ROOT)
            return user
        except FileNotFoundError:
            username = input("Enter username (e.g. bubba): ").strip()
            return cls(username)


# ────────────────────────────────────────────────
# Message Creation
# ────────────────────────────────────────────────

def create_message(to: str, subject: str, body: str, from_user: str, 
                   delivery_date: Optional[str] = None, 
                   attachment_coord: Optional[Dict] = None) -> Dict:
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
# Send (drop into runway)
# ────────────────────────────────────────────────

def send_message(user: UserState, eye: OdinsEye, msg: Dict):
    msg_bytes = json.dumps(msg).encode()
    coord = eye.encode(msg_bytes)

    if msg["delivery_date"]:
        user.queue.append({"msg": msg, "coord": coord})
        print(f"Message queued for delivery on {msg['delivery_date']}")
    else:
        user.sent.append({"msg": msg, "coord": coord})
        print("Message sent (dropped into runway)")

    user.save()


# ────────────────────────────────────────────────
# Real Runway Polling / Scanning
# ────────────────────────────────────────────────

def poll_inbox(user: UserState, eye: OdinsEye):
    print(f"Polling {user.username}@odin runway: {GLOBAL_ROOT} → {RUNWAY_END}")

    current = max(user.last_checked_mask, GLOBAL_ROOT)
    batch_end = min(current + POLL_BATCH_SIZE, RUNWAY_END)

    found_count = 0

    for mask in range(current, batch_end, POLL_STEP_SIZE):
        for guess_len in LENGTH_GUESSES:
            try:
                coord = {
                    "version": "0.1.1",
                    "start_mask": GLOBAL_ROOT,
                    "end_mask": mask,
                    "anchor_mask": mask - 8,
                    "last_choice": 0,
                    "last_direction": 1,
                    "length_bytes": guess_len
                }
                data = eye.decode(coord)
                prefix = MAGIC_PREFIX.encode() + user.username.encode()[:4]
                if data.startswith(prefix):
                    try:
                        payload = data[len(prefix):]
                        msg = json.loads(payload)
                        if msg["to"] == user.username:
                            if msg.get("delivery_date") and msg["delivery_date"] > datetime.now().isoformat():
                                user.queue.append({"msg": msg, "coord": coord})
                                print(f"Queued future message from {msg['from']}: {msg['subject']}")
                            else:
                                user.inbox.append({"msg": msg, "coord": coord})
                                print(f"Delivered message from {msg['from']}: {msg['subject']}")
                            found_count += 1
                            break  # stop guessing lengths for this mask
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass  # skip invalid masks

        time.sleep(POLL_THROTTLE_SEC)

    user.last_checked_mask = batch_end
    user.save()

    if found_count > 0:
        print(f"Found {found_count} new messages in this poll cycle")
    else:
        print("Poll cycle complete – no new messages")


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
    print(f"Background polling started – scanning runway every {POLL_INTERVAL_SEC}s")


# ────────────────────────────────────────────────
# CLI Interface
# ────────────────────────────────────────────────

def show_inbox(user: UserState):
    print("\nInbox:")
    if not user.inbox:
        print("  (empty)")
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


def show_queue(user: UserState):
    print("\nQueued (future delivery):")
    if not user.queue:
        print("  (empty)")
    for i, item in enumerate(user.queue):
        msg = item["msg"]
        print(f"[{i+1}] To: {msg['to']} | Subject: {msg['subject']}")
        print(f"   Delivery: {msg['delivery_date']}")
        print("-" * 60)


def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.search_start)

    print(f"Odin Mail v0.1 – Welcome, {user.username}@odin")
    print(f"Runway: {GLOBAL_ROOT} → {RUNWAY_END}")
    print("Background polling active – messages will appear in inbox when found.")

    start_polling(user, eye)

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
            show_queue(user)

        elif cmd == "poll":
            poll_inbox(user, eye)

        elif cmd == "save":
            user.save()
            print("State saved.")

        else:
            print("Unknown command.")


if __name__ == '__main__':
    main()
