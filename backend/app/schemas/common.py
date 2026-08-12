"""
Standard API response envelope.

AIB v1.0 Vol 12.10 / Vol 14.3-14.4 — every response follows:
{
  success: bool,
  message: str,
  data: object | null,
  errors: [],
  timestamp: ISO8601
}
"""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StandardResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    errors: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_now_iso)


def success_response(message: str, data: Any = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
        "errors": [],
        "timestamp": utc_now_iso(),
    }


def error_response(message: str, errors: Optional[List[str]] = None) -> dict:
    return {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors or [],
        "timestamp": utc_now_iso(),
    }
