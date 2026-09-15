from datetime import datetime, timezone
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import DeviceStatus


class TelemetryCreate(BaseModel):
    """Payload de entrada estritamente validado com Pydantic v2 para ingestão de telemetria."""

    model_config = ConfigDict(extra="forbid")

    latitude: Annotated[
        float,
        Field(
            ...,
            ge=-90.0,
            le=90.0,
            description="Latitude geográfica (-90.0 a 90.0 graus)",
            examples=[-23.55052],
        ),
    ]
    longitude: Annotated[
        float,
        Field(
            ...,
            ge=-180.0,
            le=180.0,
            description="Longitude geográfica (-180.0 a 180.0 graus)",
            examples=[-46.633308],
        ),
    ]
    battery_level: Annotated[
        float,
        Field(
            ...,
            ge=0.0,
            le=100.0,
            description="Nível percentual de bateria (0.0 a 100.0%)",
            examples=[85.5],
        ),
    ]
    status: Annotated[
        DeviceStatus,
        Field(
            ...,
            description="Status operacional atual emitido pelo dispositivo",
            examples=[DeviceStatus.ACTIVE],
        ),
    ]
    sensor_timestamp: Annotated[
        datetime,
        Field(
            ...,
            description="Data e hora da leitura no hardware com fuso horário (ex: UTC)",
            examples=["2026-09-13T23:00:00Z"],
        ),
    ]

    @field_validator("sensor_timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Garante que o timestamp possua fuso horário (assume UTC caso omitido)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class TelemetryResponse(BaseModel):
    """Representação da telemetria persistida no histórico."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID sequencial do registro histórico")
    device_id: str = Field(..., description="ID do dispositivo emissor")
    latitude: float = Field(..., description="Latitude gravada")
    longitude: float = Field(..., description="Longitude gravada")
    battery_level: float = Field(..., description="Nível de bateria gravado")
    status: DeviceStatus = Field(..., description="Status do dispositivo no momento da leitura")
    sensor_timestamp: datetime = Field(..., description="Timestamp original do sensor")
    received_at: datetime = Field(..., description="Timestamp da recepção pelo servidor")
    is_current_state: bool = Field(
        ...,
        description="Indica se este pacote atualizou o estado consolidado (mais recente) ou foi apenas arquivado no histórico",
    )
