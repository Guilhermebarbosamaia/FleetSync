from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Float, Index, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.schemas.common import DeviceStatus

if TYPE_CHECKING:
    from app.models.telemetry import TelemetryLog


class Device(Base):
    """Modelo relacional do Dispositivo da frota.
    
    Mantém os metadados cadastrais e o último estado consolidado
    (última telemetria válida por ordem de timestamp).
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, index=True, doc="Identificador único do dispositivo"
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SQLEnum(DeviceStatus, native_enum=False),
        default=DeviceStatus.IDLE,
        nullable=False,
        index=True,
        doc="Status operacional mais recente",
    )
    last_latitude: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, index=True, doc="Última latitude válida registrada"
    )
    last_longitude: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, index=True, doc="Última longitude válida registrada"
    )
    last_battery_level: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Último nível de bateria registrado (0-100)"
    )
    last_sensor_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp do sensor do pacote mais recente aceito para este dispositivo",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Data e hora de provisionamento do dispositivo no sistema",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Data e hora da última atualização do registro",
    )

    # Relacionamento com histórico de telemetrias
    telemetry_logs: Mapped[list["TelemetryLog"]] = relationship(
        "TelemetryLog",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="TelemetryLog.sensor_timestamp.desc()",
    )

    __table_args__ = (
        Index("ix_devices_last_coords", "last_latitude", "last_longitude"),
    )
