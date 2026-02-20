# odin_mail.py
# Odin Mail v0.1.2 – Temporal Email Client with Private Runway & Handshake
# Uses Odin's Eye as dependency
# MIT License – free for all

import json
import time
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional
import threading
from odins_eye import OdinsEye

# ────────────────────────────────────────────────
# Global Defaults
# ────────────────────────────────────────────────

GLOBAL_ROOT = 50000
MAGIC_PREFIX = b"AB42"
POLL_INTERVAL_SEC = 60
POLL_BATCH_SIZE = 1000
POLL_STEP_SIZE = 5
POLL_THROTTLE_SEC = 0.05   # 20 decodes/sec
LENGTH_GUESSES = [512, 1024, 2048, 4096]
MAX_TEXT_LENGTH = 64 * 1024
RUNWAY_LENGTH = 10000      # max masks in runway

# ────────────────────────────────────────────────
# User State
# ────────────────────────────────────────────────

class UserState:
    def __init__(self, username: str):
        self.username = username
        self.inbox: List[Dict] = []
        self.sent: List[Dict] = []
        self.queue: List[Dict] = []
        self.private_secret = secrets.token_bytes(32)  # shared with recipient
        self.runway_start = self._compute_runway_start()
        self.last_checked_mask = self.runway_start
        self.polling = False

    def _compute_runway_start(self):
        h = hashlib.sha256(self.private_secret + self.username.encode()).digest()
        return GLOBAL_ROOT + int.from_bytes(h[:8], 'big') % 100000

    def save(self, path: str = "odin_state.json"):
        state = {
            "username": self.username,
            "inbox": self.inbox,
            "sent": self.sent,
            "queue": self.queue,
            "private_secret": self.private_secret.hex(),
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
            user.private_secret = bytes.fromhex(state["private_secret"])
            user.runway_start = state.get("runway_start", user._compute_runway_start())
            user.last_checked_mask = state.get("last_checked_mask", user.runway_start)
            user.inbox = state.get("inbox", [])
            user.sent = state.get("sent", [])
            user.queue = state.get("queue", [])
            return user
        except FileNotFoundError:
            username = input("Enter username: ").strip()
            user = cls(username)
            user.save()
            return user


# ────────────────────────────────────────────────
# RNG Handshake (shared phrase → verification code)
# ────────────────────────────────────────────────

def generate_handshake_code(phrase: str, seed: bytes) -> bytes:
    """Simple RNG handshake: phrase + seed → 8-byte code"""
    rng = secrets.SystemRandom()
    h = hashlib.sha256(phrase.encode() + seed).digest()
    rng.seed(h)
    return rng.randbytes(8)


def verify_handshake_code(phrase: str, seed: bytes, received_code: bytes) -> bool:
    expected = generate_handshake_code(phrase, seed)
    return expected == received_code


# ────────────────────────────────────────────────
# Message Creation & Send (with handshake)
# ────────────────────────────────────────────────

def create_message(to: str, subject: str, body: str, from_user: str, 
                   delivery_date: Optional[str] = None, 
                   attachment_coord: Optional[Dict] = None,
                   handshake_phrase: str = "odin") -> Dict:
    handshake_seed = secrets.token_bytes(16)
    code = generate_handshake_code(handshake_phrase, handshake_seed)
    msg = {
        "from": from_user,
        "to": to,
        "subject": subject,
        "body": body[:MAX_TEXT_LENGTH],
        "sent_date": datetime.now().isoformat(),
        "delivery_date": delivery_date,
        "attachment": attachment_coord,
        "handshake_seed": handshake_seed.hex(),
        "handshake_code": code.hex(),
        "status": "queued" if delivery_date else "sent"
    }
    return msg


def send_message(user: UserState, eye: OdinsEye, msg: Dict):
    payload = json.dumps(msg).encode()
    length_bytes = len(payload).to_bytes(4, 'big')
    hash_prefix = hashlib.sha256(payload).digest()[:4]
    prefixed = length_bytes + hash_prefix + payload

    coord = eye.encode(prefixed)

    if coord["end_mask"] > user.runway_start + RUNWAY_LENGTH:
        print("Warning: message exceeded runway length")

    if msg["delivery_date"]:
        user.queue.append({"msg": msg, "coord": coord})
        print(f"Queued for {msg['delivery_date']}")
    else:
        user.sent.append({"msg": msg, "coord": coord})
        print("Sent (dropped into private runway)")

    user.save()


# ────────────────────────────────────────────────
# Polling with Prefix + Length + Handshake Verification
# ────────────────────────────────────────────────

def poll_inbox(user: UserState, eye: OdinsEye):
    runway_start = user.runway_start
    runway_end = runway_start + RUNWAY_LENGTH

    print(f"Polling {user.username}@odin private runway: {runway_start} → {runway_end}")

    current = max(user.last_checked_mask, runway_start)
    batch_end = min(current + POLL_BATCH_SIZE, runway_end)

    found_count = 0

    for mask in range(current, batch_end, POLL_STEP_SIZE):
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
                        # Verify handshake (assume shared phrase "odin")
                        if verify_handshake_code("odin", bytes.fromhex(msg["handshake_seed"]), bytes.fromhex(msg["handshake_code"])):
                            if msg.get("delivery_date") and msg["delivery_date"] > datetime.now().isoformat():
                                user.queue.append({"msg": msg, "coord": coord_full})
                                print(f"Queued future message from {msg['from']}: {msg['subject']}")
                            else:
                                user.inbox.append({"msg": msg, "coord": coord_full})
                                print(f"Delivered message from {msg['from']}: {msg['subject']}")
                            found_count += 1
                            break
        except Exception:
            pass

        time.sleep(POLL_THROTTLE_SEC)

    user.last_checked_mask = batch_end
    user.save()

    print(f"Poll cycle complete – {found_count} new messages")


# ────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────

def main():
    user = UserState.load()
    eye = OdinsEye(start_mask=user.runway_start)

    print(f"Odin Mail v0.1.2 – Welcome, {user.username}@odin")
    print(f"Private runway: {user.runway_start} → {user.runway_start + RUNWAY_LENGTH}")
    print("Background polling active.")

    start_polling(user, eye)

    while True:
        print("\nCommands: compose | inbox | queue | poll | save | exit")
        cmd = input("> ").strip().lower()

        if cmd == "exit":
            user.polling = False
            user.save()
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
            print("Saved.")

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
    print("Polling started.")

if __name__ == '__main__':
    main()
