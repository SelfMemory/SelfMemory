"""Migrate existing plaintext memory data to encrypted format.

Usage:
    python scripts/migrate_encrypt_data.py --dry-run
    python scripts/migrate_encrypt_data.py
    python scripts/migrate_encrypt_data.py --batch-size 50

Requires:
    MASTER_ENCRYPTION_KEY env var to be set.
    QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME env vars for Qdrant connection.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from selfmemory.security.encryption import encrypt_payload

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_qdrant_client() -> QdrantClient:
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def migrate(dry_run: bool, batch_size: int) -> None:
    master_key = os.environ.get("MASTER_ENCRYPTION_KEY", "")
    if not master_key:
        logger.error("MASTER_ENCRYPTION_KEY env var is required")
        sys.exit(1)

    collection = os.environ.get("QDRANT_COLLECTION_NAME", "selfmemory")
    client = get_qdrant_client()

    encrypted_count = 0
    skipped_count = 0
    failed_count = 0
    offset = None

    logger.info(
        "Starting migration (dry_run=%s, collection=%s, batch_size=%d)",
        dry_run,
        collection,
        batch_size,
    )

    while True:
        results, next_offset = client.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        for point in results:
            payload = point.payload

            if payload.get("encrypted"):
                skipped_count += 1
                continue

            if not (payload.get("project_id") or payload.get("user_id")):
                logger.warning(
                    "Point %s has no project_id or user_id, skipping", point.id
                )
                failed_count += 1
                continue

            try:
                encrypted = encrypt_payload(payload, master_key)

                if not dry_run:
                    client.set_payload(
                        collection_name=collection,
                        payload=encrypted,
                        points=[point.id],
                    )

                encrypted_count += 1
            except Exception:
                logger.exception("Failed to encrypt point %s", point.id)
                failed_count += 1

        if next_offset is None:
            break
        offset = next_offset

    action = "Would encrypt" if dry_run else "Encrypted"
    logger.info(
        "Migration complete: %s=%d, skipped=%d, failed=%d",
        action,
        encrypted_count,
        skipped_count,
        failed_count,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encrypt existing memory data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of points to process per batch (default: 100)",
    )
    args = parser.parse_args()
    migrate(dry_run=args.dry_run, batch_size=args.batch_size)
