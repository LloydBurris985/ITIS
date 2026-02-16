#!/usr/bin/env python3
"""
odins_undelete.py
Undelete / recover files using Odin's Eye coordinates
Part of the Odin Project / ITIS

MIT License - free for all
"""

import argparse
import json
from odins_eye import OdinsEye   # ← uses our engine as dependency

def main():
    parser = argparse.ArgumentParser(description="Odin's Eye Undelete Tool")
    sub = parser.add_subparsers(dest='mode', required=True)

    # Mode 1: Direct recovery from known coordinate (most common "undelete")
    direct = sub.add_parser('recover', help='Recover file from saved coordinate')
    direct.add_argument('--coord', required=True, help='Path to coord.json or JSON string')
    direct.add_argument('--output', required=True, help='Output filename')

    # Mode 2: Future extension - Hill-climbing search (stub for now)
    search = sub.add_parser('search', help='[Future] Search lattice for matching file')
    search.add_argument('--file', help='Known corrupted/deleted file to match against')

    args = parser.parse_args()

    eye = OdinsEye()

    if args.mode == 'recover':
        # Load coordinate
        if args.coord.endswith('.json'):
            with open(args.coord) as f:
                coord = json.load(f)
        else:
            coord = json.loads(args.coord)

        print(f"Recovering {coord['length_bytes']} bytes from coordinate...")
        recovered = eye.decode(coord)

        with open(args.output, 'wb') as f:
            f.write(recovered)

        print(f"✓ Successfully recovered to: {args.output}")
        print(f"   Size: {len(recovered)} bytes")
        print(f"   Start mask: {coord['start_mask']}")

    elif args.mode == 'search':
        print("Hill-climbing search coming in v0.2")
        print("Will search the lattice for coordinates that match a target file/hash.")

if __name__ == '__main__':
    main()