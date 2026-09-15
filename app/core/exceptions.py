from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class FleetPulseException(Exception):
    """Exceção base de domínio para a aplicação FleetPulse."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class DeviceNotFoundError(FleetPulseException):
    """Lançada quando um dispositivo solicitado não é encontrado no sistema."""

    def __init__(self, device_id: str) -> None:
        super().__init__(
            message=f"Dispositivo '{device_id}' não encontrado.",
            details={"device_id": device_id},
        )
        self.device_id = device_id


class InvalidBoundingBoxError(FleetPulseException):
    """Lançada quando as coordenadas de um bounding box geográfico são inválidas ou inconsistentes."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(message=message, details=details)


def setup_exception_handlers(app: FastAPI) -> None:
    """Registra os exception handlers no FastAPI para desacoplar erros de domínio de HTTPExceptions."""

    @app.exception_handler(DeviceNotFoundError)
    async def device_not_found_handler(
        request: Request, exc: DeviceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "DEVICE_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidBoundingBoxError)
    async def invalid_bounding_box_handler(
        request: Request, exc: InvalidBoundingBoxError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "INVALID_BOUNDING_BOX",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(FleetPulseException)
    async def generic_domain_handler(
        request: Request, exc: FleetPulseException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "BUSINESS_RULE_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )
