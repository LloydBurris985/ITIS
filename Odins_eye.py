# odins_eye.py
# Odin's Eye v0.1 – Base-64 Oscillator for Odin Project / ITIS
# MIT License – free for all[](https://opensource.org/licenses/MIT)

class OdinsEye:
    """Base-64 oscillating encoder/decoder with bounded reset bounce."""

    LOW = 10000
    HIGH = 99999
    STEP_FACTOR = 8
    CENTER = 32

    def __init__(self, start_mask: int = 50000):
        """Initialize with starting mask (root)."""
        self.start_mask = start_mask

    def encode(self, data: bytes) -> dict:
        """
        Encode bytes to a compact coordinate dict.
        Returns: {'start_mask', 'end_mask', 'prev_mask', 'end_d', 'length_bytes'}
        """
        if not data:
            return {
                "start_mask": self.start_mask,
                "end_mask": self.start_mask,
                "prev_mask": self.start_mask,
                "end_d": 0,
                "length_bytes": 0
            }

        current = self.start_mask
        direction = 1
        prev_current = None

        # Convert to 6-bit chunks
        bit_string = ''.join(f'{b:08b}' for b in data)
        chunks = [int(bit_string[i:i+6], 2) for i in range(0, len(bit_string), 6)]
        if len(bit_string) % 6 != 0:
            chunks[-1] <<= 6 - len(bit_string) % 6

        for d in chunks:
            delta = direction * (d - self.CENTER) * self.STEP_FACTOR
            next_current = current + delta

            # Reset bounce
            if next_current > self.HIGH:
                next_current = self.LOW
                direction = 1
            elif next_current < self.LOW:
                next_current = self.HIGH
                direction = -1

            prev_current = current
            current = next_current

        return {
            "start_mask": self.start_mask,
            "end_mask": current,
            "prev_mask": prev_current if prev_current is not None else self.start_mask,
            "end_d": chunks[-1] if chunks else 0,
            "length_bytes": len(data)
        }

    def decode(self, coord: dict) -> bytes:
        """
        Decode from coordinate dict back to original bytes.
        Requires: start_mask, end_mask, prev_mask, end_d, length_bytes
        """
        end_mask = coord["end_mask"]
        prev_mask = coord["prev_mask"]
        end_d = coord["end_d"]
        length_bytes = coord["length_bytes"]

        if length_bytes == 0:
            return b''

        bits = []
        current = end_mask

        # Anchor last step with prev_mask + end_d
        delta = (end_d - self.CENTER) * self.STEP_FACTOR
        expected_prev = end_mask - delta
        direction = 1

        if expected_prev != prev_mask:
            # Likely reset on last step
            if end_mask == self.LOW:
                expected_prev = prev_mask - delta + (self.HIGH - self.LOW)
                direction = 1
            elif end_mask == self.HIGH:
                expected_prev = prev_mask - delta - (self.HIGH - self.LOW)
                direction = -1
            if expected_prev != prev_mask:
                raise ValueError("Anchor mismatch: prev_mask does not match calculated previous")

        bits.append(end_d)
        current = prev_mask

        # Backward loop for remaining chunks
        chunks_needed = (length_bytes * 8 + 5) // 6 - 1
        for _ in range(chunks_needed):
            found = False
            for d in range(64):
                delta = direction * (d - self.CENTER) * self.STEP_FACTOR
                prev = current - delta

                if self.LOW <= prev <= self.HIGH:
                    bits.append(d)
                    current = prev
                    found = True
                    break

                # Reset detection
                if current == self.LOW and prev > self.HIGH:
                    bits.append(d)
                    current = prev - (self.HIGH - self.LOW)
                    direction = 1
                    found = True
                    break
                if current == self.HIGH and prev < self.LOW:
                    bits.append(d)
                    current = prev + (self.HIGH - self.LOW)
                    direction = -1
                    found = True
                    break

            if not found:
                raise ValueError(f"Backward decode failed at step {len(bits)}")

        # Reverse bits and convert to bytes
        bits = bits[::-1]
        bit_str = ''.join(f'{b:06b}' for b in bits)
        bit_str = bit_str[:length_bytes * 8]  # trim to exact original bit length

        byte_data = [int(bit_str[i:i+8], 2) for i in range(0, len(bit_str), 8)]
        return bytes(byte_data)


# ────────────────────────────────────────────────
# Simple command-line interface (optional)
# ────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Odin's Eye v0.1 – Oscillator Demo")
    sub = parser.add_subparsers(dest='cmd', required=True)

    enc = sub.add_parser('encode', help='Encode file to coord')
    enc.add_argument('file')
    enc.add_argument('--start', type=int, default=50000)

    dec = sub.add_parser('decode', help='Decode from coord')
    dec.add_argument('--start', type=int, required=True)
    dec.add_argument('--end', type=int, required=True)
    dec.add_argument('--prev', type=int, required=True)
    dec.add_argument('--d', type=int, required=True)
    dec.add_argument('--len', type=int, required=True)
    dec.add_argument('output')

    args = parser.parse_args()
    eye = OdinsEye(start_mask=args.start if hasattr(args, 'start') else 50000)

    if args.cmd == 'encode':
        with open(args.file, 'rb') as f:
            data = f.read()
        coord = eye.encode(data)
        print("Coordinate:")
        print(coord)
    else:
        coord = {
            "start_mask": args.start,
            "end_mask": args.end,
            "prev_mask": args.prev,
            "end_d": args.d,
            "length_bytes": args.len
        }
        data = eye.decode(coord)
        with open(args.output, 'wb') as f:
            f.write(data)
        print(f"Decoded {len(data)} bytes to {args.output}")