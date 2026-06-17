import uuid
from typing import Optional

from domain.models import NotificationRecord, NotificationRequestIn, RequestStatus


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self._records: dict[str, NotificationRecord] = {}

    def create(self, data: NotificationRequestIn) -> NotificationRecord:
        record = NotificationRecord(
            id=str(uuid.uuid4()),
            to=data.to,
            message=data.message,
            type=data.type,
        )
        self._records[record.id] = record
        return record

    def get(self, request_id: str) -> Optional[NotificationRecord]:
        return self._records.get(request_id)

    def start_processing(self, request_id: str) -> NotificationRecord:
        record = self._records[request_id]
        record.status = RequestStatus.processing
        return record


_repository = InMemoryNotificationRepository()


def get_repository() -> InMemoryNotificationRepository:
    return _repository
