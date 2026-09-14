from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core_api.models import ClientNotice


def queue_notice(db: Session, event_key: str, text: str, callback_data: str | None = None) -> None:
    db.execute(
        insert(ClientNotice)
        .values(id=uuid4(), event_key=event_key, text=text, callback_data=callback_data)
        .on_conflict_do_nothing(index_elements=["event_key"])
    )
