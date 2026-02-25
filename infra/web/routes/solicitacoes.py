from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, Query, BackgroundTasks
from application.dtos.solicitacao import CreateLocalDTO, LocalResponse, SolicitacaoDisplay, CreateSolicitacao, AnexosDisplay
from infra.web.dependencies import get_solicitacao_service, SolicitacaoService
from infra.db.repos import UserDomain
from infra.web.auth import get_current_user
from domain.entities.user import Roles
from uuid import UUID
from infra.providers import EmailProvider, StorageProvider
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/requests", tags=["Request"])
storage = StorageProvider()
email_provider: EmailProvider = EmailProvider()
   
@router.post("/local", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def create_local(dtos: CreateLocalDTO,
                       current_user: UserDomain = Depends(get_current_user), 
                       service: SolicitacaoService = Depends(get_solicitacao_service)):
    if not current_user.role == Roles.ADMIN.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    await service.create_local(dtos)
    return

@router.get("/locais", response_model=list[LocalResponse], dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def list_locais(city: str, state: str, 
                      service: SolicitacaoService = Depends(get_solicitacao_service)) -> list[LocalResponse]:
    locais = await service.local_repo.get_by_city(city, state)
    return locais

@router.get("/local", response_model=LocalResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_local(local_id: UUID, service: SolicitacaoService = Depends(get_solicitacao_service)) -> LocalResponse:
    local = await service.local_repo.get_by_id(local_id)
    return LocalResponse(id=local.id, nome=local.nome, estado=local.estado, cidade=local.cidade)


@router.get(
    "/local/solicitacoes",
    response_model=list[SolicitacaoDisplay], dependencies=[Depends(RateLimiter(times=25, seconds=60))]
)
async def get_solicitacoes(
    local_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: UserDomain = Depends(get_current_user),
    service: SolicitacaoService = Depends(get_solicitacao_service)
) -> list[SolicitacaoDisplay]:

    if current_user.role != Roles.ADMIN.value:
        raise HTTPException(status_code=401, detail="Usuário não autorizado")

    offset = (page - 1) * limit

    result = await service.solicitacao_repo.get_by_local_id(
        local_id=local_id,
        limit=limit,
        offset=offset
    )

    return result

@router.get("/local/solicitacao", response_model=SolicitacaoDisplay, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_solicitacao(solicitacao_id: UUID, current_user: UserDomain = Depends(get_current_user),
                          service:SolicitacaoService = Depends(get_solicitacao_service))->SolicitacaoDisplay:
    if not current_user.role == Roles.ADMIN.value:
        raise HTTPException(status_code=401, detail="Usuário não autorizado")
    
    response = await service.solicitacao_repo.get_by_id_for_user(solicitacao_id)
    return response

@router.post("/local/solicitacao", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def create_solicitacao(
    dtos: CreateSolicitacao,
    background_tasks: BackgroundTasks,
    service: SolicitacaoService = Depends(get_solicitacao_service),
) -> UUID:

    new = await service.create_solicitacao(dto=dtos)

    admins = await service.user_repo.get_admins()
    
    background_tasks.add_task(
        email_provider.aviso_model,
        admins,
        new
    )

    return new.id

@router.post("/local/solicitacao/anexo", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def anexar_arquivo(file: UploadFile,
                         solicitacao_id: UUID = Form(...),
                         service: SolicitacaoService = Depends(get_solicitacao_service)) -> list[AnexosDisplay]:
    try:
        anexos = await service.solicitacao_repo.add_anexo(solicitacao_id, files=[file])
        return anexos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao tentar enviar arquivo ao supabase: {e}")

@router.put("/local/solicitacao/status", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def update_status(solicitacao_id: UUID,
                        new_status: str,
                        service: SolicitacaoService = Depends(get_solicitacao_service),
                        current_user: UserDomain = Depends(get_current_user)):
    if current_user.role != Roles.ADMIN.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    if new_status not in ["criado", "em_andamento", "concluido"]:
        raise HTTPException(status_code=400, detail="Status inválido")
    await service.update_status(solicitacao_id=solicitacao_id, status=new_status)
    return

@router.get("/solicitacoes/status", dependencies=[Depends(RateLimiter(times=25, seconds=60))])
async def get_solicitacoes_por_status(status: str, 
                                      page: int, 
                                      limit: int,
                                      current_user: UserDomain = Depends(get_current_user),
                                      service: SolicitacaoService = Depends(get_solicitacao_service)) -> list[SolicitacaoDisplay]:
    if current_user.role != Roles.ADMIN.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    if status not in ["criado", "em_andamento", "concluido"]:
        raise HTTPException(status_code=400, detail="Status inválido")
    offset = (page-1)*limit
    response = await service.solicitacao_repo.get_by_status(status, limit, offset)
    return response