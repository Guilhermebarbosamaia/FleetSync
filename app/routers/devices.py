from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Path, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.common import DeviceStatus, PaginatedResponse
from app.schemas.device import DeviceFilterParams, DeviceStateResponse
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse
from app.services.device_service import DeviceService
from app.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/devices", tags=["Devices & Telemetry"])


def get_telemetry_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TelemetryService:
    """Dependency provider para o TelemetryService."""
    return TelemetryService(db_session=db, redis_client=redis)


def get_device_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> DeviceService:
    """Dependency provider para o DeviceService."""
    return DeviceService(db_session=db, redis_client=redis)


@router.post(
    "/{device_id}/telemetry",
    response_model=TelemetryResponse,
    summary="Ingestão de telemetria do dispositivo",
    description=(
        "Recebe telemetria do dispositivo, valida dados rigorosamente e grava no histórico bruto. "
        "Se o sensor_timestamp for mais recente que o último consolidado, atualiza o estado no Postgres/Redis "
        "e retorna HTTP 201. Se for pacote fora de ordem ou duplicado, grava apenas no histórico e retorna HTTP 200."
    ),
    responses={
        201: {
            "description": "Telemetria aceita e estado atual do dispositivo consolidado",
            "model": TelemetryResponse,
        },
        200: {
            "description": "Telemetria arquivada no histórico, mas estado atual inalterado (pacote atrasado/duplicado)",
            "model": TelemetryResponse,
        },
    },
)
async def ingest_telemetry(
    device_id: Annotated[str, Path(..., description="ID único do dispositivo")],
    payload: TelemetryCreate,
    response: Response,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
) -> TelemetryResponse:
    """Endpoint de ingestão de telemetria com desacoplamento de status HTTP."""
    telemetry_record, is_current = await service.process_telemetry(
        device_id=device_id, payload=payload
    )

    response.status_code = (
        status.HTTP_201_CREATED if is_current else status.HTTP_200_OK
    )
    return telemetry_record


@router.get(
    "/{device_id}/state",
    response_model=DeviceStateResponse,
    summary="Consulta o estado atual do dispositivo",
    description="Retorna o estado consolidado mais recente do dispositivo via cache Redis (com fallback para Postgres).",
    responses={
        404: {
            "description": "Dispositivo não encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "error": "DEVICE_NOT_FOUND",
                        "message": "Dispositivo 'xyz' não encontrado.",
                        "details": {"device_id": "xyz"},
                    }
                }
            },
        }
    },
)
async def get_device_state(
    device_id: Annotated[str, Path(..., description="ID único do dispositivo")],
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceStateResponse:
    """Endpoint para recuperar o estado atual do dispositivo."""
    return await service.get_device_state(device_id=device_id)


@router.get(
    "",
    response_model=PaginatedResponse[DeviceStateResponse],
    summary="Listagem paginada de dispositivos da frota",
    description=(
        "Lista os dispositivos cadastrados com suporte a filtros por status e bounding box geográfico "
        "(min_lat, max_lat, min_lon, max_lon) e paginação com limit e offset."
    ),
)
async def list_devices(
    service: Annotated[DeviceService, Depends(get_device_service)],
    status: Annotated[Optional[DeviceStatus], Query(description="Filtrar por status operacional")] = None,
    min_lat: Annotated[Optional[float], Query(ge=-90.0, le=90.0, description="Latitude mínima do bounding box")] = None,
    max_lat: Annotated[Optional[float], Query(ge=-90.0, le=90.0, description="Latitude máxima do bounding box")] = None,
    min_lon: Annotated[Optional[float], Query(ge=-180.0, le=180.0, description="Longitude mínima do bounding box")] = None,
    max_lon: Annotated[Optional[float], Query(ge=-180.0, le=180.0, description="Longitude máxima do bounding box")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Quantidade de registros por página")] = 50,
    offset: Annotated[int, Query(ge=0, description="Deslocamento para paginação")] = 0,
) -> PaginatedResponse[DeviceStateResponse]:
    """Endpoint para listagem paginada e filtrada de dispositivos."""
    # A instanciação de DeviceFilterParams dispara a validação de consistência geográfica
    filter_params = DeviceFilterParams(
        status=status,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )
    return await service.list_devices(filter_params)
