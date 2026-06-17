from domain.models import (
    NotificationCreatedOut,
    NotificationRequestIn,
    NotificationStatusOut,
    RequestStatus,
)
from domain.repository import InMemoryNotificationRepository, get_repository
from fastapi import APIRouter, Depends, HTTPException, Response, status
from services import pipeline

router = APIRouter(prefix="/requests", tags=["Notifications"])


@router.post(
    "",
    response_model=NotificationCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    payload: NotificationRequestIn,
    repository: InMemoryNotificationRepository = Depends(get_repository),
) -> NotificationCreatedOut:
    record = repository.create(payload)
    return NotificationCreatedOut(id=record.id)


@router.post("/{request_id}/process", response_model=NotificationStatusOut)
def process_request(
    request_id: str,
    response: Response,
    repository: InMemoryNotificationRepository = Depends(get_repository),
) -> NotificationStatusOut:
    record = repository.get(request_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    # only the first call enqueues, a repeat call just returns the current status
    if record.status == RequestStatus.queued:
        record = repository.start_processing(request_id)
        pipeline.enqueue(request_id)
        response.status_code = status.HTTP_202_ACCEPTED

    return NotificationStatusOut(id=record.id, status=record.status)


@router.get("/{request_id}", response_model=NotificationStatusOut)
def get_request(
    request_id: str,
    repository: InMemoryNotificationRepository = Depends(get_repository),
) -> NotificationStatusOut:
    record = repository.get(request_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )
    return NotificationStatusOut(id=record.id, status=record.status)
