from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Classe base declarativa do SQLAlchemy 2.0 com suporte a atributos assíncronos."""
    pass
