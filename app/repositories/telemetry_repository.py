from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryLog
from app.schemas.telemetry import TelemetryCreate


class TelemetryRepository:
    """Repositório assíncrono para gravação incondicional de telemetrias no Postgres/TimescaleDB."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_log(
        self, device_id: str, payload: TelemetryCreate
    ) -> TelemetryLog:
        """Grava incondicionalmente a telemetria recebida no log bruto (série temporal imutável)."""
        log_entry = TelemetryLog(
            device_id=device_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            battery_level=payload.battery_level,
            status=payload.status,
            sensor_timestamp=payload.sensor_timestamp,
        )
        self.session.add(log_entry)
        await self.session.flush()
        await self.session.refresh(log_entry)
        return log_entry
