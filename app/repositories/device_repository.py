from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.schemas.common import DeviceStatus


class DeviceRepository:
    """Repositório assíncrono para operações de persistência e consulta do modelo Device."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, device_id: str, for_update: bool = False
    ) -> Optional[Device]:
        """Busca um dispositivo por ID, opcionalmente aplicando FOR UPDATE para controle de concorrência."""
        stmt = select(Device).where(Device.id == device_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, device: Device) -> Device:
        """Cria e persiste um novo dispositivo no banco de dados."""
        self.session.add(device)
        await self.session.flush()
        await self.session.refresh(device)
        return device

    async def update(self, device: Device) -> Device:
        """Sincroniza as alterações do dispositivo com a sessão."""
        await self.session.flush()
        await self.session.refresh(device)
        return device

    async def list_devices(
        self,
        status: Optional[DeviceStatus] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Device], int]:
        """Consulta paginada de dispositivos com filtros opcionais por status e bounding box geográfico."""
        base_query = select(Device)
        count_query = select(func.count(Device.id))

        if status is not None:
            base_query = base_query.where(Device.status == status)
            count_query = count_query.where(Device.status == status)

        if (
            min_lat is not None
            and max_lat is not None
            and min_lon is not None
            and max_lon is not None
        ):
            geo_filter = (
                (Device.last_latitude >= min_lat)
                & (Device.last_latitude <= max_lat)
                & (Device.last_longitude >= min_lon)
                & (Device.last_longitude <= max_lon)
            )
            base_query = base_query.where(geo_filter)
            count_query = count_query.where(geo_filter)

        # Executa contagem total
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one() or 0

        # Aplica ordenação estável e paginação
        stmt = base_query.order_by(Device.updated_at.desc(), Device.id.asc()).limit(limit).offset(offset)
        items_result = await self.session.execute(stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def get_all_devices(self) -> list[Device]:
        """Recupera todos os dispositivos cadastrados para o snapshot da frota."""
        stmt = select(Device).order_by(Device.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
