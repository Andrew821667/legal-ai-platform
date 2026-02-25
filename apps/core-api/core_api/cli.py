from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from core_api.db import SessionLocal
from core_api.models import (
    ApiKey,
    ContractJob,
    Event,
    InputMode,
    Lead,
    LeadSource,
    ScheduledPost,
    ScheduledPostStatus,
    Scope,
)
from core_api.security import generate_api_key, hash_api_key


def create_admin_key(name: str, if_no_keys: bool) -> int:
    with SessionLocal() as db:
        if if_no_keys:
            existing = db.execute(select(ApiKey.id).where(ApiKey.scope == Scope.admin, ApiKey.is_active.is_(True))).first()
            if existing:
                print("Admin key already exists, skipped.")
                return 0

        plain_key = generate_api_key()
        row = ApiKey(name=name, scope=Scope.admin, key_hash=hash_api_key(plain_key), is_active=True)
        db.add(row)
        db.commit()
        print(f"Admin API key created: {plain_key}")
        return 0


def seed_dev_data() -> int:
    with SessionLocal() as db:
        lead = Lead(source=LeadSource.telegram_bot, name="Test Lead", contact="@test_user")
        db.add(lead)
        db.flush()

        event = Event(lead_id=lead.id, type="bot_start", payload={"seed": True})
        db.add(event)

        post = ScheduledPost(
            text="Seed scheduled post",
            publish_at=datetime.now(timezone.utc) + timedelta(days=1),
            status=ScheduledPostStatus.draft,
        )
        db.add(post)

        job = ContractJob(
            lead_id=lead.id,
            input_mode=InputMode.text_only,
            document_text="Seed contract text",
        )
        db.add(job)

        db.commit()
        print("Seed data created.")
        return 0


def cleanup_idempotency(hours: int = 24) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    from core_api.models import IdempotencyKey

    with SessionLocal() as db:
        result = db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff))
        db.commit()
        print(f"Deleted idempotency rows: {result.rowcount or 0}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Core API CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-admin-key")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--if-no-keys", action="store_true")

    subparsers.add_parser("seed-dev-data")

    cleanup_parser = subparsers.add_parser("cleanup-idempotency")
    cleanup_parser.add_argument("--hours", type=int, default=24)

    args = parser.parse_args()

    if args.command == "create-admin-key":
        return create_admin_key(name=args.name, if_no_keys=args.if_no_keys)
    if args.command == "seed-dev-data":
        return seed_dev_data()
    if args.command == "cleanup-idempotency":
        return cleanup_idempotency(hours=args.hours)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
