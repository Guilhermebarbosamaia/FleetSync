import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Realtime WebSocket"])


@router.websocket("/fleet")
async def websocket_fleet_endpoint(websocket: WebSocket) -> None:
    """Endpoint WebSocket para monitoramento em tempo real de toda a frota.
    
    Fluxo de Conexão:
    1. Aceita a conexão do cliente (websocket.accept).
    2. Envia um snapshot inicial completo com o estado mais recente de cada dispositivo.
    3. Assina o canal de Pub/Sub do Redis ('fleet:telemetry').
    4. Encaminha continuamente para o cliente qualquer atualização de telemetria publicada.
    5. Gerencia desconexões e garante liberação graciosa dos recursos de Pub/Sub e conexões.
    """
    await websocket.accept()
    logger.info("Cliente WebSocket conectado ao /ws/fleet")

    redis_client = await get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        # 1. Recupera e envia snapshot inicial da frota
        async with AsyncSessionLocal() as session:
            device_service = DeviceService(
                db_session=session, redis_client=redis_client
            )
            snapshot = await device_service.get_fleet_snapshot()

            snapshot_payload = {
                "type": "snapshot",
                "count": len(snapshot),
                "data": [item.model_dump(mode="json") for item in snapshot],
            }
            await websocket.send_text(json.dumps(snapshot_payload))

        # 2. Assina o canal de telemetria no Redis
        await pubsub.subscribe(settings.REDIS_PUBSUB_CHANNEL)

        # 3. Monitora simultaneamente mensagens do Redis e desconexão do cliente
        async def forward_pubsub_messages() -> None:
            """Consome mensagens do Redis Pub/Sub e envia via WebSocket."""
            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    payload_str = message.get("data")
                    if isinstance(payload_str, bytes):
                        payload_str = payload_str.decode("utf-8")
                    await websocket.send_text(payload_str)

        async def listen_for_client_disconnect() -> None:
            """Aguarda sinal de desconexão ou mensagens enviadas pelo cliente."""
            while True:
                # Mantém leitura ativa para capturar disconnect ou frames de ping do cliente
                await websocket.receive_text()

        forward_task = asyncio.create_task(forward_pubsub_messages())
        disconnect_task = asyncio.create_task(listen_for_client_disconnect())

        done, pending = await asyncio.wait(
            [forward_task, disconnect_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info("Cliente desconectado de /ws/fleet")
    except Exception as exc:
        logger.error(
            "Erro inesperado na sessão WebSocket /ws/fleet: %s", exc, exc_info=True
        )
    finally:
        # 4. Liberação graciosa dos recursos
        try:
            await pubsub.unsubscribe(settings.REDIS_PUBSUB_CHANNEL)
            await pubsub.aclose()
        except Exception:
            pass
        await redis_client.aclose()
