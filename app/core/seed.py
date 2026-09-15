from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.schemas.common import DeviceStatus


DEFAULT_DEVICES = (
    {"id": "fleet-001", "status": DeviceStatus.ACTIVE, "latitude": -23.5505, "longitude": -46.6333, "battery_level": 94.0},
    {"id": "fleet-002", "status": DeviceStatus.ACTIVE, "latitude": -23.5614, "longitude": -46.6559, "battery_level": 81.0},
    {"id": "fleet-003", "status": DeviceStatus.IDLE, "latitude": -23.5896, "longitude": -46.6581, "battery_level": 67.0},
    {"id": "fleet-004", "status": DeviceStatus.MAINTENANCE, "latitude": -23.5275, "longitude": -46.6786, "battery_level": 52.0},
    {"id": "fleet-005", "status": DeviceStatus.ACTIVE, "latitude": -23.5955, "longitude": -46.6853, "battery_level": 88.0},
    {"id": "fleet-006", "status": DeviceStatus.OFFLINE, "latitude": -23.5489, "longitude": -46.6388, "battery_level": 23.0},
    {"id": "fleet-007", "status": DeviceStatus.ERROR, "latitude": -23.5707, "longitude": -46.6455, "battery_level": 39.0},
    {"id": "fleet-008", "status": DeviceStatus.IDLE, "latitude": -23.5163, "longitude": -46.6250, "battery_level": 73.0},
)


async def seed_default_devices(session: AsyncSession) -> int:
    """Cadastra dispositivos de demonstração sem alterar os já existentes."""
    device_ids = [device["id"] for device in DEFAULT_DEVICES]
    result = await session.execute(select(Device.id).where(Device.id.in_(device_ids)))
    existing_ids = set(result.scalars().all())

    new_devices = [
        Device(
            id=device["id"],
            status=device["status"],
            last_latitude=device["latitude"],
            last_longitude=device["longitude"],
            last_battery_level=device["battery_level"],
        )
        for device in DEFAULT_DEVICES
        if device["id"] not in existing_ids
    ]

    if not new_devices:
        return 0

    session.add_all(new_devices)
    await session.commit()
    return len(new_devices)