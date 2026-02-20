# odin_mail.py
# Odin Mail v0.1.3 – Temporal Email Client with Polished Polling
# Uses Odin's Eye as dependency
# MIT License – free for all

import json
import time
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional
import threading
import logging
from odins_eye import OdinsEye

# ────────────────────────────────────────────────
# Logging Setup
# ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("OdinMail")

# ────────────────────────────────────────────────
# Global Defaults
# ────────────────────────────────────────────────

MAGIC_PREFIX = b"AB42"
POLL_INTERVAL_SEC = 60
POLL_BATCH_SIZE = 1000
POLL_STEP_SIZE = 5
POLL_THROTTLE_SEC = 0.05   # 20 decodes/sec
MAX_TEXT_LENGTH = 64 * 1024
DEFAULT_RUNWAY_LENGTH = 10000

# ────────────────────────────────────────────────
# User State
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []
        self.sent: List[Dict] = []
        self.queue: List[Dict] = []
        self.runway_start = 50000  # configurable
        self.last_checked_mask = self.runway_start
        self.polling = False

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
            return cls(username)


# ────────────────────────────────────────────────
# Message Creation & Send (with length + hash prefix)
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


def send_message(user: UserState, eye: OdinsEye, msg: Dict):
    payload = json.dumps(msg).encode()
    length_bytes = len(payload).to_bytes(4, 'big')
    hash_prefix = hashlib.sha256(payload).digest()[:4]
    prefixed = length_bytes + hash_prefix + payload

    coord = eye.encode(prefixed)

    runway_end = user.runway_start + DEFAULT_RUNWAY_LENGTH
    if coord["end_mask"] > runway_end:
        logger.warning("Message exceeded runway end – consider larger runway")

    if msg["delivery_date"]:
        user.queue.append({"msg": msg, "coord": coord})
        logger.info(f"Queued for {msg['delivery_date']}")
    else:
        user.sent.append({"msg": msg, "coord": coord})
        logger.info("Sent (dropped into runway)")

    user.save()


# ────────────────────────────────────────────────
# Polling with Length + Hash Prefix (single attempt)
# ────────────────────────────────────────────────

def poll_inbox(user: UserState, eye: OdinsEye):
    runway_start = user.runway_start
    runway_end = runway_start + DEFAULT_RUNWAY_LENGTH

    logger.info(f"Polling {user.username}@odin runway: {runway_start} → {runway_end}")

    current = max(user.last_checked_mask, runway_start)
    batch_end = min(current + POLL_BATCH_SIZE, runway_end)

    found_count = 0
    masks_checked = 0

    for mask in range(current, batch_end, POLL_STEP_SIZE):
        masks_checked += 1
        try:
            # Decode first 8 bytes (length + hash prefix)
            coord_short = {
                "version": "0.1.1",
                "start_mask": runway_start,
                "end_mask": mask,
                "anchor_mask": mask - 8,
                "last_choice": 0,
                "last_direction": 1,
                "length_bytes": 8
            }
            short_data = eye.decode(coord_short)
            if len(short_data) < 8:
                continue

            length_bytes = int.from_bytes(short_data[:4], 'big')
            hash_prefix = short_data[4:8]

            # Full decode
            coord_full = coord_short.copy()
            coord_full["length_bytes"] = length_bytes + 8
            data = eye.decode(coord_full)

            prefix = MAGIC_PREFIX.encode() + user.username.encode()[:4]
            if data.startswith(prefix):
                payload = data[len(prefix):]
                computed_hash = hashlib.sha256(payload).digest()[:4]
                if computed_hash == hash_prefix:
                    msg = json.loads(payload)
                    if msg["to"] == user.username:
                        if msg.get("delivery_date") and msg["delivery_date"] > datetime.now().isoformat():
                            user.queue.append({"msg": msg, "coord": coord_full})
                            logger.info(f"Queued future message from {msg['from']}: {msg['subject']}")
                        else:
                            user.inbox.append({"msg": msg, "coord": coord_full})
                            logger.info(f"Delivered message from {msg['from']}: {msg['subject']}")
                        found_count += 1
                        break
        except Exception as e:
            logger.debug(f"Skipped mask {mask}: {str(e)}")

        time.sleep(POLL_THROTTLE_SEC)

    user.last_checked_mask = batch_end
    user.save()

    logger.info(f"Poll cycle complete – {masks_checked} masks checked, {found_count} messages found")


def start_polling(user: UserState, eye: OdinsEye):
    if user.polling:
        return
    user.polling = True

    def loop():
        while user.polling:
            poll_inbox(user, eye)
            time.sleep(POLL_INTERVAL_SEC)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    logger.info("Background polling started")


# ────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────

def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.runway_start)

    logger.info(f"Odin Mail v0.1.3 – Welcome, {user.username}@odin")
    logger.info(f"Runway: {user.runway_start} → {user.runway_start + DEFAULT_RUNWAY_LENGTH} (configurable)")

    start_polling(user, eye)

    while True:
        print("\nCommands: compose | inbox | queue | poll | save | set_runway | reset | exit")
        cmd = input("> ").strip().lower()

        if cmd == "exit":
            user.polling = False
            user.save()
            logger.info("Goodbye.")
            break

        elif cmd == "compose":
            to = input("To: ")
            subject = input("Subject: ")
            body = input("Body:\n")
            delivery = input("Delivery date or blank: ").strip() or None
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
            logger.info("State saved.")

        elif cmd == "set_runway":
            new_start = int(input("New runway start mask: "))
            user.runway_start = new_start
            user.last_checked_mask = new_start
            user.save()
            logger.info(f"Runway start updated to {new_start}")

        elif cmd == "reset":
            user.last_checked_mask = user.runway_start
            user.save()
            logger.info("Scan reset to runway start")

        else:
            print("Unknown command.")

def show_inbox(user: UserState):
    print("\nInbox:")
    for i, item in enumerate(user.inbox):
        msg = item["msg"]
        print(f"[{i+1}] From: {msg['from']} | Subject: {msg['subject']}")
        print(f"   Sent: {msg['sent_date']}")
        print(f"   Body preview: {msg['body'][:100]}...")
        if msg.get("attachment"):
            print(f"   Attachment coord: {msg['attachment']}")
        print("-" * 60)

def show_queue(user: UserState):
    print("\nQueued:")
    for i, item in enumerate(user.queue):
        msg = item["msg"]
        print(f"[{i+1}] To: {msg['to']} | Subject: {msg['subject']} | Delivery: {msg['delivery_date']}")
        print("-" * 60)

def start_polling(user: UserState, eye: OdinsEye):
    if user.polling:
        return
    user.polling = True

    def loop():
        while user.polling:
            poll_inbox(user, eye)
            time.sleep(POLL_INTERVAL_SEC)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    logger.info("Polling started.")

if __name__ == '__main__':
    main()
