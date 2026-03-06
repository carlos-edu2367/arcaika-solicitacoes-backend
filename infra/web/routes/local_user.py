from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from infra.web.dependencies import get_local_user_service, get_solicitacao_service, LocalUserService, SolicitacaoService
from infra.web.auth import get_current_local_user, LocalUserDomain
from application.dtos.solicitacao import SolicitacaoDisplay, UpdateSolicitacaoDTO, Prioridade
from domain.entities.locais import LocalRoles
from domain.entities.solicitacao import Status
from uuid import UUID
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(prefix="/local_user", tags=["Local User"])

class UpdateSolicitacaoWEB(BaseModel):
    solicitacao_id: UUID
    assunto: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    descricao: Optional[str] = None
    prioridade: Optional[Prioridade] = None
    nome_da_unidade: Optional[str] = None
    informacoes_adicionais: Optional[str] = None

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
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    
    response = await service.solicitacao_repo.get_by_id_for_user(solicitacao_id)
    if response.local_id != current_user.local_id:
        raise HTTPException(status_code=403, detail="Você não tem permissão para ver essa solicitação.")
    
    return response

@router.put("/solicitacoes/editar", dependencies=[Depends(RateLimiter(times=25, seconds=60))])
async def editar_solicitacao(dtos: UpdateSolicitacaoWEB, current_user: LocalUserDomain = Depends(get_current_local_user),
                             service: SolicitacaoService = Depends(get_solicitacao_service)):
    if not current_user.role == LocalRoles.LOCAL_USER.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    
    solicitacao = await service.solicitacao_repo.get_by_id(dtos.solicitacao_id)
    if solicitacao.local.id != current_user.local_id:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    
    if solicitacao.status != Status.CRIADO.value:
        raise HTTPException(status_code=400, detail="Não é possível editar uma solicitação em andamento/concluída")
    
    
    await service.update_solicitacao(UpdateSolicitacaoDTO(
        solicitacao_id=solicitacao.id,
        assunto=dtos.assunto,
        nome=dtos.nome,
        email=dtos.email,
        telefone=dtos.telefone,
        descricao=dtos.descricao,
        prioridade=dtos.prioridade,
        nome_da_unidade=dtos.nome_da_unidade,
        informacoes_adicionais=dtos.informacoes_adicionais
    ))
    return