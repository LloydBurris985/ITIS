# odins_eye.py
# Odin's Eye v0.1.1 â€“ Base-64 Oscillator for Odin Project / ITIS
# MIT License â€“ free for all

import hashlib
from typing import Dict, Iterator

class OdinsEye:
    """Base-64 oscillating navigator with reset bounce and streaming support."""

    LOW = 10000
    HIGH = 99999
    STEP_FACTOR = 8
    CENTER = 32
    VERSION = "0.1.1"

    def __init__(self, start_mask: int = 50000):
        self.start_mask = start_mask

    def encode(self, data: bytes) -> Dict[str, any]:
        """Encode bytes â†’ improved coordinate dict with hash & direction."""
        if not data:
            return {
                "version": self.VERSION,
                "start_mask": self.start_mask,
                "end_mask": self.start_mask,
                "anchor_mask": self.start_mask,
                "last_choice": 0,
                "last_direction": 1,
                "length_bytes": 0,
                "original_hash": hashlib.sha256(b'').hexdigest()
            }

        current = self.start_mask
        direction = 1
        anchor = None

        bit_string = ''.join(f'{b:08b}' for b in data)
        chunks = [int(bit_string[i:i+6], 2) for i in range(0, len(bit_string), 6)]
        if len(bit_string) % 6 != 0:
            chunks[-1] <<= 6 - len(bit_string) % 6

        for d in chunks:
            delta = direction * (d - self.CENTER) * self.STEP_FACTOR
            next_current = current + delta

            if next_current > self.HIGH:
                next_current = self.LOW
                direction = 1
            elif next_current < self.LOW:
                next_current = self.HIGH
                direction = -1

            anchor = current
            current = next_current

        file_hash = hashlib.sha256(data).hexdigest()

        return {
            "version": self.VERSION,
            "start_mask": self.start_mask,
            "end_mask": current,
            "anchor_mask": anchor if anchor is not None else self.start_mask,
            "last_choice": chunks[-1] if chunks else 0,
            "last_direction": direction,
            "length_bytes": len(data),
            "original_hash": file_hash
        }

    def decode(self, coord: Dict[str, any]) -> bytes:
        """Decode from coordinate dict back to original bytes with hash check."""
        version = coord.get("version")
        if version not in [self.VERSION, "0.1"]:
            print(f"Warning: Coordinate version {version} â€“ may be incompatible")

        end_mask = coord["end_mask"]
        anchor_mask = coord["anchor_mask"]
        last_choice = coord["last_choice"]
        last_direction = coord.get("last_direction", 1)
        length_bytes = coord["length_bytes"]
        expected_hash = coord.get("original_hash")

        if length_bytes == 0:
            recovered = b''
        else:
            bit_buffer = []  # list to prepend
            bit_buffer.insert(0, f'{last_choice:06b}')
            current = anchor_mask
            direction = last_direction

            # Anchor last step verification
            delta = (last_choice - self.CENTER) * self.STEP_FACTOR
            expected_prev = end_mask - direction * delta
            if expected_prev != anchor_mask:
                if end_mask == self.LOW:
                    expected_prev = anchor_mask - direction * delta + (self.HIGH - self.LOW)
                    direction = 1
                elif end_mask == self.HIGH:
                    expected_prev = anchor_mask - direction * delta - (self.HIGH - self.LOW)
                    direction = -1
                if expected_prev != anchor_mask:
                    raise ValueError("Anchor mismatch â€“ coordinate may be invalid")

            # Backward loop for remaining chunks
            total_chunks = (length_bytes * 8 + 5) // 6
            remaining_chunks = total_chunks - 1

            while remaining_chunks > 0:
                found = False
                for d in range(64):
                    delta = direction * (d - self.CENTER) * self.STEP_FACTOR
                    prev = current - delta

                    if self.LOW <= prev <= self.HIGH:
                        bit_buffer.insert(0, f'{d:06b}')
                        current = prev
                        found = True
                        break

                    if current == self.LOW and prev > self.HIGH:
                        bit_buffer.insert(0, f'{d:06b}')
                        current = prev - (self.HIGH - self.LOW)
                        direction = 1
                        found = True
                        break
                    if current == self.HIGH and prev < self.LOW:
                        bit_buffer.insert(0, f'{d:06b}')
                        current = prev + (self.HIGH - self.LOW)
                        direction = -1
                        found = True
                        break

                if not found:
                    raise ValueError("Backward decode failed â€“ no valid previous mask")

                remaining_chunks -= 1

            bit_str = ''.join(bit_buffer)[:length_bytes * 8]
            byte_data = [int(bit_str[i:i+8], 2) for i in range(0, len(bit_str), 8)]
            recovered = bytes(byte_data)

        # Hash verification (strong safety)
        if expected_hash and hashlib.sha256(recovered).hexdigest() != expected_hash:
            raise ValueError("Hash mismatch â€“ recovered data does not match original")

        return recovered

    def decode_stream(self, coord: Dict[str, any], chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        """
        Streaming decoder â€“ yields chunks for large files (10 GB+).
        """
        bit_buffer = ""
        bytes_yielded = 0
        total_bits = coord["length_bytes"] * 8

        # Full backward walk, but yield as bytes fill
        end_mask = coord["end_mask"]
        anchor_mask = coord["anchor_mask"]
        last_choice = coord["last_choice"]
        last_direction = coord.get("last_direction", 1)
        length_bytes = coord["length_bytes"]

        bit_buffer += f'{last_choice:06b}'
        current = anchor_mask

        # Anchor last step (same as decode)
        delta = (last_choice - self.CENTER) * self.STEP_FACTOR
        expected_prev = end_mask - last_direction * delta
        direction = last_direction

        if expected_prev != anchor_mask:
            if end_mask == self.LOW:
                expected_prev = anchor_mask - last_direction * delta + (self.HIGH - self.LOW)
                direction = 1
            elif end_mask == self.HIGH:
                expected_prev = anchor_mask - last_direction * delta - (self.HIGH - self.LOW)
                direction = -1
            if expected_prev != anchor_mask:
                raise ValueError("Anchor mismatch")

        # Backward loop
        total_chunks = (total_bits + 5) // 6
        remaining_chunks = total_chunks - 1

        while remaining_chunks > 0:
            found = False
            for d in range(64):
                delta = direction * (d - self.CENTER) * self.STEP_FACTOR
                prev = current - delta

                if self.LOW <= prev <= self.HIGH:
                    bit_buffer += f'{d:06b}'
                    current = prev
                    found = True
                    break

                if current == self.LOW and prev > self.HIGH:
                    bit_buffer += f'{d:06b}'
                    current = prev - (self.HIGH - self.LOW)
                    direction = 1
                    found = True
                    break
                if current == self.HIGH and prev < self.LOW:
                    bit_buffer += f'{d:06b}'
                    current = prev + (self.HIGH - self.LOW)
                    direction = -1
                    found = True
                    break

            if not found:
                raise ValueError("Backward decode failed")

            remaining_chunks -= 1

            # Yield when buffer has enough for a chunk
            while len(bit_buffer) >= 8:
                byte_str = bit_buffer[:8]
                byte = int(byte_str, 2)
                yield bytes([byte])
                bytes_yielded += 1
                bit_buffer = bit_buffer[8:]

                if bytes_yielded >= length_bytes:
                    return

        # Final flush
        while len(bit_buffer) >= 8:
            byte_str = bit_buffer[:8]
            byte = int(byte_str, 2)
            yield bytes([byte])
            bytes_yielded += 1
            bit_buffer = bit_buffer[8:]

    def decode_to_file(self, coord: Dict[str, any], output_path: str, chunk_size: int = 1024*1024):
        """Stream decode directly to disk â€“ ideal for 10 GB+ lattice sections."""
        total_written = 0
        with open(output_path, 'wb') as f:
            for chunk in self.decode_stream(coord, chunk_size):
                f.write(chunk)
                total_written += len(chunk)
        print(f"âœ“ Saved {total_written:,} bytes to {output_path}")
