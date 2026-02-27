from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from infra.web.dependencies import get_local_user_service, get_solicitacao_service, LocalUserService, SolicitacaoService
from infra.web.auth import get_current_local_user, LocalUserDomain
from application.dtos.solicitacao import SolicitacaoDisplay
from domain.entities.locais import LocalRoles
from uuid import UUID

router = APIRouter(prefix="/local_user", tags=["Local User"])

@router.get("/solicitacoes", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def get_solicitacoes( page: int, limit: int,
                            current_user: LocalUserDomain = Depends(get_current_local_user),
                            service: SolicitacaoService = Depends(get_solicitacao_service)) -> list[SolicitacaoDisplay]:
    if current_user.role != LocalRoles.LOCAL_USER.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    
    offset = (page-1) * limit

    response = await service.solicitacao_repo.get_by_local_id(local_id=current_user.local_id, limit=limit, offset=offset)
    return response

@router.get("/solicitacao", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_solicitacao(solicitacao_id: UUID, current_user: LocalUserDomain = Depends(get_current_local_user),
                          service:SolicitacaoService = Depends(get_solicitacao_service))->SolicitacaoDisplay:
    if not current_user.role == LocalRoles.LOCAL_USER.value:
        raise HTTPException(status_code=401, detail="Usuário não autorizado")
    
    response = await service.solicitacao_repo.get_by_id_for_user(solicitacao_id)
    if response.local_id != current_user.local_id:
        raise HTTPException(status_code=403, detail="Você não tem permissão para ver essa solicitação.")
    
    return response