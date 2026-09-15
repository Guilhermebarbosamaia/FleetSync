import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.device import Device
from app.models.telemetry import TelemetryLog
from app.repositories.device_repository import DeviceRepository
from app.repositories.redis_repository import RedisRepository
from app.repositories.telemetry_repository import TelemetryRepository
from app.schemas.device import DeviceStateResponse
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse

logger = logging.getLogger(__name__)


class TelemetryService:
    """Serviço responsável pelo processamento de telemetria, ordenação e consolidação de estado.
    
    Decisão de Design - Descarte e Ordenação de Pacotes Fora de Ordem:
    -----------------------------------------------------------------
    1. Resiliência a Redes IoT / Celulares Instáveis:
       Dispositivos embarcados frequentemente sofrem intermitência de sinal, enfileirando
       mensagens localmente. Ao recuperar a conectividade, pacotes podem chegar fora de ordem
       (ex: um pacote gerado às 10:00 chega depois de um pacote gerado às 10:05), ou pacotes
       duplicados podem ser reenviados por retentativas no nível de transporte (TCP/MQTT).
       
    2. Duplo Papel: Histórico Imutável vs. Estado Consolidado:
       - Histórico Bruto (Postgres / TimescaleDB): Todo e qualquer pacote recebido é
         gravado incondicionalmente na tabela 'telemetry_logs'. Isso preserva a fidelidade
         histórica para auditoria, relatórios analíticos e séries temporais do TimescaleDB.
       - Estado Atual Consolidado ('devices' no Postgres & Cache no Redis): O estado
         atual reflete a realidade física mais recente conhecida do veículo. Portanto,
         ele SÓ é atualizado se 'payload.sensor_timestamp' for estritamente mais recente
         que 'device.last_sensor_timestamp'.
         
    3. Controle de Concorrência e Atomicidade:
       Para evitar race conditions em ingestões paralelas do mesmo dispositivo, o registro
       na tabela 'devices' é bloqueado pessimistamente via 'SELECT ... FOR UPDATE' durante a
       transação. Isso garante que a verificação de precedência temporal seja estritamente
       serializável.
       
    4. Desacoplamento via Pub/Sub:
       Apenas atualizações que representam um novo estado mais recente são publicadas no
       canal Redis Pub/Sub, impedindo que consumidores em tempo real (como o WebSocket /ws/fleet)
       recebam dados retrógrados ou oscilações espúrias na interface.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> None:
        self.session = db_session
        self.redis = redis_client
        self.device_repo = DeviceRepository(db_session)
        self.telemetry_repo = TelemetryRepository(db_session)
        self.redis_repo = RedisRepository(redis_client)

    async def process_telemetry(
        self,
        device_id: str,
        payload: TelemetryCreate,
    ) -> tuple[TelemetryResponse, bool]:
        """Processa a telemetria recebida, persistindo o histórico e atualizando o estado se for mais recente.
        
        Args:
            device_id: Identificador único do dispositivo emissor.
            payload: Dados de telemetria estritamente validados pelo Pydantic v2.
            
        Returns:
            Uma tupla contendo (TelemetryResponse, is_current_state).
            - is_current_state = True: O pacote atualizou o estado consolidado (retorna 201).
            - is_current_state = False: O pacote é mais antigo ou duplicado, gravado apenas no histórico (retorna 200).
        """
        # 1. Bloqueia pessimistamente a linha do dispositivo para avaliação concorrencial segura
        device = await self.device_repo.get_by_id(device_id, for_update=True)

        is_current_state = False

        if device is None:
            # Auto-provisionamento de dispositivo novo
            device = Device(
                id=device_id,
                status=payload.status,
                last_latitude=payload.latitude,
                last_longitude=payload.longitude,
                last_battery_level=payload.battery_level,
                last_sensor_timestamp=payload.sensor_timestamp,
            )
            device = await self.device_repo.create(device)
            is_current_state = True
        else:
            # Verifica se o pacote recebido é estritamente mais recente que o último consolidado
            is_newer = (
                device.last_sensor_timestamp is None
                or payload.sensor_timestamp > device.last_sensor_timestamp
            )

            if is_newer:
                device.status = payload.status
                device.last_latitude = payload.latitude
                device.last_longitude = payload.longitude
                device.last_battery_level = payload.battery_level
                device.last_sensor_timestamp = payload.sensor_timestamp
                device = await self.device_repo.update(device)
                is_current_state = True

        # 2. Grava incondicionalmente o pacote no log bruto de telemetria.
        # O dispositivo precisa existir antes para respeitar a chave estrangeira.
        log_entry: TelemetryLog = await self.telemetry_repo.save_log(
            device_id=device_id, payload=payload
        )

        # Confirma a transação no banco de dados relacional
        await self.session.commit()

        # 3. Se for o estado mais recente, atualiza o Redis e publica no canal Pub/Sub
        if is_current_state:
            state_response = DeviceStateResponse(
                device_id=device.id,
                status=device.status,
                latitude=device.last_latitude,
                longitude=device.last_longitude,
                battery_level=device.last_battery_level,
                sensor_timestamp=device.last_sensor_timestamp,
                updated_at=device.updated_at,
            )

            state_json = state_response.model_dump_json()

            try:
                # Atualiza o cache de estado atual no Redis
                await self.redis_repo.set_state(device_id, state_json)

                # Publica evento de atualização no canal de Pub/Sub
                pubsub_envelope = json.dumps(
                    {
                        "type": "telemetry_update",
                        "data": state_response.model_dump(mode="json"),
                    }
                )
                await self.redis_repo.publish_state_update(pubsub_envelope)
            except Exception as e:
                logger.error(
                    "Falha ao atualizar Redis para o dispositivo '%s': %s",
                    device_id,
                    e,
                    exc_info=True,
                )

        response_dto = TelemetryResponse(
            id=log_entry.id,
            device_id=log_entry.device_id,
            latitude=log_entry.latitude,
            longitude=log_entry.longitude,
            battery_level=log_entry.battery_level,
            status=log_entry.status,
            sensor_timestamp=log_entry.sensor_timestamp,
            received_at=log_entry.received_at,
            is_current_state=is_current_state,
        )

        return response_dto, is_current_state
