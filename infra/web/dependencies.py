from infra.db.repos import LocalRepositoryINFRA, SolicitacaoRepositoryINFRA, UOWProviderINFRA, AsyncSession, UserRepositoryINFRA
from application.services.user_Service import UserService
from application.services.solicitacao_service import SolicitacaoService
from infra.providers import INFRAHashProvider
from fastapi import Depends
from infra.db.setup import get_db

def get_user_repo(session:AsyncSession):
    return UserRepositoryINFRA(session)

def get_solicitacao_repo(session: AsyncSession):
    return SolicitacaoRepositoryINFRA(session)

def get_local_repo(session: AsyncSession):
    return LocalRepositoryINFRA(session)

def get_infra_hash():
    return INFRAHashProvider()

def get_uow(session: AsyncSession):
    return UOWProviderINFRA(session)

def get_user_service(session: AsyncSession = Depends(get_db)):
    return UserService(
        user_repo=get_user_repo(session),
        hash_provider=get_infra_hash(),
        uow=get_uow(session)
    )

def get_solicitacao_service(session: AsyncSession = Depends(get_db)):
    return SolicitacaoService(
        user_repo=get_user_repo(session),
        uow=get_uow(session),
        solicitacao_repo=get_solicitacao_repo(session),
        local_repo=get_local_repo(session)
    )