def poll_inbox(user: UserState, eye: OdinsEye):
    # Pre-agreed limited runway for messages
    runway_start = 50000   # agreed root
    runway_end = 60000     # agreed end – no messages beyond this

    print(f"Polling {user.username}@odin runway: {runway_start} → {runway_end}")

    current = max(user.last_checked_mask, runway_start)
    batch_end = min(current + POLL_BATCH_SIZE, runway_end)

    found_count = 0

    for mask in range(current, batch_end, POLL_STEP_SIZE):
        for guess_len in LENGTH_GUESSES:
            try:
                coord = {
                    "version": "0.1.1",
                    "start_mask": runway_start,
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
                            break
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        time.sleep(POLL_THROTTLE_SEC)

    user.last_checked_mask = batch_end
    user.save()

    print(f"Poll cycle complete – {found_count} new messages found")
