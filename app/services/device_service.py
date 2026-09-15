import logging
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.exceptions import DeviceNotFoundError
from app.repositories.device_repository import DeviceRepository
from app.repositories.redis_repository import RedisRepository
from app.schemas.common import PaginatedResponse
from app.schemas.device import DeviceFilterParams, DeviceStateResponse

logger = logging.getLogger(__name__)


class DeviceService:
    """Serviço para gerenciamento e consulta de estado de dispositivos da frota."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> None:
        self.session = db_session
        self.redis = redis_client
        self.device_repo = DeviceRepository(db_session)
        self.redis_repo = RedisRepository(redis_client)

    async def get_device_state(self, device_id: str) -> DeviceStateResponse:
        """Recupera o estado atual do dispositivo adotando o padrão Cache-Aside.
        
        Ordem de resolução:
        1. Consulta o Redis para máxima performance em leituras frequentes.
        2. Em caso de cache-miss, busca no PostgreSQL.
        3. Se encontrado no banco relacional, reaquece o cache no Redis.
        4. Se não existir em nenhum dos dois, lança DeviceNotFoundError (mapeado para HTTP 404).
        """
        # 1. Tenta recuperar do Redis
        try:
            cached_state = await self.redis_repo.get_state(device_id)
            if cached_state is not None:
                return DeviceStateResponse.model_validate(cached_state)
        except Exception as e:
            logger.warning(
                "Falha ao consultar cache Redis para device '%s': %s",
                device_id,
                e,
            )

        # 2. Fallback para o PostgreSQL
        device = await self.device_repo.get_by_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id=device_id)

        state_response = DeviceStateResponse(
            device_id=device.id,
            status=device.status,
            latitude=device.last_latitude,
            longitude=device.last_longitude,
            battery_level=device.last_battery_level,
            sensor_timestamp=device.last_sensor_timestamp,
            updated_at=device.updated_at,
        )

        # 3. Reaquece o cache no Redis
        try:
            await self.redis_repo.set_state(
                device_id, state_response.model_dump_json()
            )
        except Exception as e:
            logger.warning(
                "Falha ao reaecer cache Redis para device '%s': %s",
                device_id,
                e,
            )

        return state_response

    async def list_devices(
        self, params: DeviceFilterParams
    ) -> PaginatedResponse[DeviceStateResponse]:
        """Consulta paginada de dispositivos com filtros opcionais de status e bounding box."""
        items, total = await self.device_repo.list_devices(
            status=params.status,
            min_lat=params.min_lat,
            max_lat=params.max_lat,
            min_lon=params.min_lon,
            max_lon=params.max_lon,
            limit=params.limit,
            offset=params.offset,
        )

        device_states = [
            DeviceStateResponse(
                device_id=d.id,
                status=d.status,
                latitude=d.last_latitude,
                longitude=d.last_longitude,
                battery_level=d.last_battery_level,
                sensor_timestamp=d.last_sensor_timestamp,
                updated_at=d.updated_at,
            )
            for d in items
        ]

        return PaginatedResponse(
            total=total,
            limit=params.limit,
            offset=params.offset,
            items=device_states,
        )

    async def get_fleet_snapshot(self) -> list[DeviceStateResponse]:
        """Recupera o estado de todos os dispositivos para o snapshot inicial do WebSocket."""
        devices = await self.device_repo.get_all_devices()
        return [
            DeviceStateResponse(
                device_id=d.id,
                status=d.status,
                latitude=d.last_latitude,
                longitude=d.last_longitude,
                battery_level=d.last_battery_level,
                sensor_timestamp=d.last_sensor_timestamp,
                updated_at=d.updated_at,
            )
            for d in devices
        ]
