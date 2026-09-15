from datetime import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.exceptions import InvalidBoundingBoxError
from app.schemas.common import DeviceStatus


class DeviceStateResponse(BaseModel):
    """Representação do estado atual de um dispositivo (retornado do Redis ou Postgres)."""

    model_config = ConfigDict(from_attributes=True)

    device_id: str = Field(..., description="Identificador do dispositivo")
    status: DeviceStatus = Field(..., description="Status operacional mais recente")
    latitude: Optional[float] = Field(None, description="Última latitude válida consolidada")
    longitude: Optional[float] = Field(None, description="Última longitude válida consolidada")
    battery_level: Optional[float] = Field(None, description="Último nível de bateria consolidado")
    sensor_timestamp: Optional[datetime] = Field(
        None, description="Timestamp da última telemetria válida consolidada"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp de consolidação da última atualização"
    )


class DeviceFilterParams(BaseModel):
    """Parâmetros de filtro e paginação para consulta da frota."""

    status: Optional[DeviceStatus] = Field(None, description="Filtro opcional por status do dispositivo")
    min_lat: Annotated[Optional[float], Field(None, ge=-90.0, le=90.0, description="Latitude mínima do bounding box")] = None
    max_lat: Annotated[Optional[float], Field(None, ge=-90.0, le=90.0, description="Latitude máxima do bounding box")] = None
    min_lon: Annotated[Optional[float], Field(None, ge=-180.0, le=180.0, description="Longitude mínima do bounding box")] = None
    max_lon: Annotated[Optional[float], Field(None, ge=-180.0, le=180.0, description="Longitude máxima do bounding box")] = None
    limit: Annotated[int, Field(50, ge=1, le=100, description="Quantidade máxima de itens por página")] = 50
    offset: Annotated[int, Field(0, ge=0, description="Offset de paginação")] = 0

    @model_validator(mode="after")
    def validate_bounding_box(self) -> "DeviceFilterParams":
        """Valida a integridade do bounding box geográfico quando fornecido."""
        coords = [self.min_lat, self.max_lat, self.min_lon, self.max_lon]
        provided_count = sum(1 for c in coords if c is not None)

        if 0 < provided_count < 4:
            raise InvalidBoundingBoxError(
                message="Bounding box incompleto. Todos os parâmetros (min_lat, max_lat, min_lon, max_lon) devem ser informados juntos.",
                details={
                    "min_lat": self.min_lat,
                    "max_lat": self.max_lat,
                    "min_lon": self.min_lon,
                    "max_lon": self.max_lon,
                },
            )

        if provided_count == 4:
            assert self.min_lat is not None and self.max_lat is not None
            assert self.min_lon is not None and self.max_lon is not None

            if self.min_lat > self.max_lat:
                raise InvalidBoundingBoxError(
                    message="min_lat não pode ser maior que max_lat.",
                    details={"min_lat": self.min_lat, "max_lat": self.max_lat},
                )
            if self.min_lon > self.max_lon:
                raise InvalidBoundingBoxError(
                    message="min_lon não pode ser maior que max_lon.",
                    details={"min_lon": self.min_lon, "max_lon": self.max_lon},
                )

        return self
