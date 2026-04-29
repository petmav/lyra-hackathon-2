from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ModuleNotFoundError:  # pragma: no cover - local dev without optional crypto wheel
    Ed25519PublicKey = None


def stable_hash(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def verify_signature(packet_hash: str, signature: str) -> bool:
    scheme, _, payload = signature.partition(":")
    if scheme == "sha256-fallback":
        return payload == hashlib.sha256(packet_hash.encode("utf-8")).hexdigest()
    if scheme != "ed25519" or Ed25519PublicKey is None:
        return False
    raw = base64.b64decode(payload)
    if len(raw) != 96:
        return False
    sig, pubkey = raw[:64], raw[64:]
    Ed25519PublicKey.from_public_bytes(pubkey).verify(sig, packet_hash.encode("utf-8"))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Praetor audit packet JSON sidecar.")
    parser.add_argument("json_sidecar", type=Path)
    parser.add_argument("--signature", required=True, help="signature string from the audit packet row")
    args = parser.parse_args()

    sidecar = json.loads(args.json_sidecar.read_text(encoding="utf-8"))
    packet_hash = sidecar.pop("packet_hash", None)
    if not packet_hash:
        print("missing packet_hash", file=sys.stderr)
        return 1
    computed = stable_hash(sidecar)
    if computed != packet_hash:
        print(f"hash mismatch: expected {packet_hash}, computed {computed}", file=sys.stderr)
        return 1
    try:
        signature_ok = verify_signature(packet_hash, args.signature)
    except Exception as exc:
        print(f"signature verification failed: {exc}", file=sys.stderr)
        return 1
    if not signature_ok:
        print("signature verification failed", file=sys.stderr)
        return 1
    print("audit packet verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
