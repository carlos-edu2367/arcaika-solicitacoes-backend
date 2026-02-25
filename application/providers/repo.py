from abc import ABC, abstractmethod
from domain.entities import locais, solicitacao, user
from uuid import UUID
from application.dtos.solicitacao import SolicitacaoDisplay, AnexosDisplay
from typing import List, Tuple

class UserRepo(ABC):
    
    @abstractmethod
    async def get_by_email(self, email: str) -> user.User:
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID) -> user.User:
        pass

    @abstractmethod
    async def get_admins(self) -> List[tuple[str, str]]:
        pass

    @abstractmethod
    async def save(self, user: user.User):
        pass

class LocalRepo(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> locais.Local:
        pass

    @abstractmethod
    async def get_by_city(self, city: str, state: str) -> list[locais.Local] | None:
        pass

    @abstractmethod
    async def save(self, local: locais.Local):
        pass

class SolicitacaoRepo(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> solicitacao.Solicitacao:
        pass

    @abstractmethod
    async def get_by_id_for_user(self, id: UUID) -> SolicitacaoDisplay:
        pass

    @abstractmethod
    async def get_by_local_id(self,
    local_id: UUID,
    limit: int = 10,
    offset: int = 0) -> list[SolicitacaoDisplay]:
        pass

    @abstractmethod
    async def get_by_status(self, status: solicitacao.Status, limit: int = 10,
                            offset: int = 0) -> list[SolicitacaoDisplay]:
        pass

    @abstractmethod
    async def save(self, solicitacao: solicitacao.Solicitacao):
        pass

    @abstractmethod
    async def add_anexo(self, solicitacao_id: UUID, files: list) -> list[AnexosDisplay]:
        pass

class UOWProvider(ABC):

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass