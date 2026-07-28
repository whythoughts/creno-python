from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Union

DateLike = Union[str, date]
DatetimeLike = Union[str, datetime]


def _parse_datetime(value: str) -> datetime:
    # datetime.fromisoformat only accepts "+00:00", not the "Z" suffix Creno's
    # API actually sends, on Python versions before 3.11.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    return _parse_datetime(value) if value else None


def to_iso(value: DatetimeLike) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(
                "datetime values passed to the Creno client must be timezone-aware "
                "(attach a tzinfo, e.g. datetime.timezone.utc)"
            )
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def to_date_str(value: DateLike) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class ServiceType:
    id: str
    resource_id: str
    name: str
    active: bool
    sort_order: int

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "ServiceType":
        return cls(
            id=data["id"],
            resource_id=data["resourceId"],
            name=data["name"],
            active=data["active"],
            sort_order=data["sortOrder"],
        )


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "Slot":
        return cls(start_at=_parse_datetime(data["startAt"]), end_at=_parse_datetime(data["endAt"]))


@dataclass(frozen=True)
class Availability:
    resource_id: str
    timezone: str
    slots: List[Slot]

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "Availability":
        return cls(
            resource_id=data["resourceId"],
            timezone=data["timezone"],
            slots=[Slot._from_api(row) for row in data["slots"]],
        )


@dataclass(frozen=True)
class Booking:
    id: str
    tenant_id: str
    resource_id: str
    service_type_id: Optional[str]
    customer_name: str
    customer_email: str
    customer_phone: Optional[str]
    start_at: datetime
    end_at: datetime
    status: str
    hold_expires_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "Booking":
        return cls(
            id=data["id"],
            tenant_id=data["tenantId"],
            resource_id=data["resourceId"],
            service_type_id=data.get("serviceTypeId"),
            customer_name=data["customerName"],
            customer_email=data["customerEmail"],
            customer_phone=data.get("customerPhone"),
            start_at=_parse_datetime(data["startAt"]),
            end_at=_parse_datetime(data["endAt"]),
            status=data["status"],
            hold_expires_at=_parse_optional_datetime(data.get("holdExpiresAt")),
            notes=data.get("notes"),
            created_at=_parse_datetime(data["createdAt"]),
        )
