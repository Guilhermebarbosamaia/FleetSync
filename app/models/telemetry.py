from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, PrimaryKeyConstraint, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.schemas.common import DeviceStatus

if TYPE_CHECKING:
    from app.models.device import Device


class TelemetryLog(Base):
    """Modelo de série temporal para o log bruto de telemetria da frota.
    
    Projetado para ser transformado em uma hypertable do TimescaleDB
    particionada por 'sensor_timestamp'. Grava incondicionalmente todos
    os pacotes recebidos (histórico imutável de telemetria).
    """

    __tablename__ = "telemetry_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        autoincrement=True,
        doc="Identificador sequencial único do registro de telemetria",
    )
    device_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Identificador do dispositivo emissor",
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Latitude do dispositivo no momento da leitura (-90.0 a 90.0)",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Longitude do dispositivo no momento da leitura (-180.0 a 180.0)",
    )
    battery_level: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Nível de carga da bateria (0.0 a 100.0)",
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SQLEnum(DeviceStatus, native_enum=False),
        nullable=False,
        doc="Status reportado pelo dispositivo na leitura",
    )
    sensor_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Timestamp original emitido pelos sensores do hardware",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp de recebimento e ingestão nos servidores do FleetPulse",
    )

    # Relacionamento de volta com o Device
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="telemetry_logs",
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", "sensor_timestamp"),
        Index("ix_telemetry_device_timestamp", "device_id", "sensor_timestamp"),
    )
