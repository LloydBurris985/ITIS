# odin_mail.py
# Odin Mail v0.1.1 – Temporal Email Client with Infinite Runway Polling
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
# Global Defaults – Pre-agreed for all users
# ────────────────────────────────────────────────

MAGIC_PREFIX = "AB42"
POLL_INTERVAL_SEC = 60
POLL_BATCH_SIZE = 500         # masks per cycle (larger for production)
POLL_STEP_SIZE = 5            # step this many masks (speed vs thoroughness)
POLL_THROTTLE_SEC = 0.2       # sleep between decode attempts (\~5/sec max)
LENGTH_GUESSES = [512, 1024, 2048, 4096]  # try these lengths
MAX_TEXT_LENGTH = 64 * 1024   # text body limit

# ────────────────────────────────────────────────
# User State
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []
        self.sent: List[Dict] = []
        self.queue: List[Dict] = []
        self.runway_start = 50000  # configurable pre-agreed root
        self.last_checked_mask = self.runway_start
        self.polling = False

    def _hash_to_start(self, username: str) -> int:
        h = hashlib.sha256(username.encode()).hexdigest()
        return int(h[:8], 16) % 100000

    def save(self, path: str = "odin_state.json"):
        state = {
            "username": self.username,
            "inbox": self.inbox,
            "sent": self.sent,
            "queue": self.queue,
            "runway_start": self.runway_start,
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
            user.runway_start = state.get("runway_start", 50000)
            user.last_checked_mask = state.get("last_checked_mask", user.runway_start)
            return user
        except FileNotFoundError:
            username = input("Enter username (e.g. bubba): ").strip()
            user = cls(username)
            user.runway_start = user._hash_to_start(username) + 50000  # auto-set
            return user


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
# Real Runway Polling / Scanning (infinite from start)
# ────────────────────────────────────────────────

def poll_inbox(user: UserState, eye: OdinsEye):
    print(f"Polling {user.username}@odin runway from {user.runway_start} onward")

    current = user.last_checked_mask
    batch_end = current + POLL_BATCH_SIZE

    found_count = 0

    for mask in range(current, batch_end, POLL_STEP_SIZE):
        for guess_len in LENGTH_GUESSES:
            try:
                coord = {
                    "version": "0.1.1",
                    "start_mask": user.runway_start,
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
                            break  # stop guessing for this mask
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        time.sleep(POLL_THROTTLE_SEC)

    user.last_checked_mask = batch_end
    user.save()

    print(f"Poll cycle complete – {found_count} new messages found")


# ────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────

def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.runway_start)

    print(f"Odin Mail v0.1 – Welcome, {user.username}@odin")
    print(f"Runway start: {user.runway_start} (infinite onward)")
    print("Background polling active – messages will appear in inbox when found.")

    start_polling(user, eye)

    while True:
        print("\nCommands: compose | inbox | queue | poll | save | set_runway | reset | exit")
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

        elif cmd == "set_runway":
            new_start = int(input("New runway start mask: "))
            user.runway_start = new_start
            user.last_checked_mask = new_start
            user.save()
            print(f"Runway start updated to {new_start}")

        elif cmd == "reset":
            user.last_checked_mask = user.runway_start
            user.save()
            print("Scan reset to runway start")

        else:
            print("Unknown command.")

if __name__ == '__main__':
    main()
