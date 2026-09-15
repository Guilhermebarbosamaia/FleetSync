import json
from typing import Any, Optional
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.config import settings


class RedisRepository:
    """Repositório para operações de cache de estado atual e pub/sub de telemetria via Redis."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _state_key(device_id: str) -> str:
        return f"device:state:{device_id}"

    async def get_state(self, device_id: str) -> Optional[dict[str, Any]]:
        """Busca o estado atual em cache para o dispositivo."""
        key = self._state_key(device_id)
        raw_data = await self.redis.get(key)
        if raw_data is None:
            return None
        return json.loads(raw_data)

    async def set_state(
        self,
        device_id: str,
        state_json: str,
        ttl_seconds: Optional[int] = settings.REDIS_STATE_TTL_SECONDS,
    ) -> None:
        """Salva o estado atual consolidado no Redis com TTL opcional."""
        key = self._state_key(device_id)
        if ttl_seconds:
            await self.redis.set(key, state_json, ex=ttl_seconds)
        else:
            await self.redis.set(key, state_json)

    async def publish_state_update(self, message_json: str) -> int:
        """Publica a atualização de estado no canal Pub/Sub da frota."""
        return await self.redis.publish(settings.REDIS_PUBSUB_CHANNEL, message_json)

    def get_pubsub(self) -> PubSub:
        """Retorna uma nova instância de PubSub do Redis para assinatura de canais."""
        return self.redis.pubsub()
