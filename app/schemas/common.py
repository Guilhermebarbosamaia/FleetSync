from enum import StrEnum
from typing import Generic, TypeVar
from pydantic import BaseModel, Field


class DeviceStatus(StrEnum):
    """Status operacionais suportados para os dispositivos da frota."""

    ACTIVE = "active"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    ERROR = "error"


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Schema genérico de resposta paginada."""

    total: int = Field(..., ge=0, description="Total de itens correspondentes ao filtro")
    limit: int = Field(..., ge=1, description="Limite máximo de itens por página")
    offset: int = Field(..., ge=0, description="Deslocamento (offset) da listagem")
    items: list[T] = Field(..., description="Lista de itens da página atual")
