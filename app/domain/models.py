from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    email = "email"
    sms = "sms"
    push = "push"


class RequestStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    sent = "sent"
    failed = "failed"


class NotificationRequestIn(BaseModel):
    to: str
    message: str
    type: NotificationType


class NotificationCreatedOut(BaseModel):
    id: str


class NotificationStatusOut(BaseModel):
    id: str
    status: RequestStatus


class NotificationRecord(BaseModel):
    id: str
    to: str
    message: str
    type: NotificationType
    status: RequestStatus = RequestStatus.queued
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
