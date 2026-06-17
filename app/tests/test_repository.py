from domain.models import NotificationRequestIn, NotificationType, RequestStatus
from domain.repository import InMemoryNotificationRepository


def _payload(type_: NotificationType = NotificationType.email) -> NotificationRequestIn:
    return NotificationRequestIn(to="user@example.com", message="hi", type=type_)


def test_create_starts_as_queued():
    repo = InMemoryNotificationRepository()
    record = repo.create(_payload())
    assert record.status == RequestStatus.queued
    assert repo.get(record.id) is record


def test_get_missing_returns_none():
    repo = InMemoryNotificationRepository()
    assert repo.get("does-not-exist") is None


def test_start_processing_transitions_to_processing():
    repo = InMemoryNotificationRepository()
    record = repo.create(_payload(NotificationType.sms))
    updated = repo.start_processing(record.id)
    assert updated.status == RequestStatus.processing
    assert repo.get(record.id).status == RequestStatus.processing


def test_mark_sent():
    repo = InMemoryNotificationRepository()
    record = repo.create(_payload(NotificationType.push))
    repo.mark_sent(record.id)
    assert repo.get(record.id).status == RequestStatus.sent


def test_mark_failed():
    repo = InMemoryNotificationRepository()
    record = repo.create(_payload(NotificationType.push))
    repo.mark_failed(record.id)
    assert repo.get(record.id).status == RequestStatus.failed


def test_records_are_independent_per_repository_instance():
    repo_a = InMemoryNotificationRepository()
    repo_b = InMemoryNotificationRepository()
    record = repo_a.create(_payload())
    assert repo_b.get(record.id) is None
