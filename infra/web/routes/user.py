from fastapi import APIRouter, HTTPException, Depends
from application.dtos.user import LoginDTOS, LoginResponse, UserInfo, UserRegisterDTOS, CreateLocalUserDTO
from application.dtos.solicitacao import CreateLocalDTO
from infra.web.dependencies import get_solicitacao_service, SolicitacaoService, get_user_service, UserService, get_local_user_service, LocalUserService
from infra.providers import TokenProvider
from infra.db.repos import UserDomain
from infra.web.auth import get_current_user
from domain.entities.user import Roles
from fastapi_limiter.depends import RateLimiter
from logging import getLogger

logger = getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])
token_provider = TokenProvider()

@router.post("/login", response_model=LoginResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def login(dtos: LoginDTOS, 
                service: UserService = Depends(get_user_service), 
                local_user_service: LocalUserService = Depends(get_local_user_service)) -> LoginResponse:
    user = await service.can_login(dtos)
    if not user:
        user = await local_user_service.can_login(dtos)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciais incorretas")
        
        user_info = UserInfo(nome=user.nome, email=user.email, role=user.role, local_id=user.local_id)
        token = token_provider.create_token(user_id=user.id, role=user.role)
        return LoginResponse(user = user_info, access_token=token, token_type="Bearer") #local

    user_info = UserInfo(nome=user.name, email=user.email, role=user.role)
    token = token_provider.create_token(user_id=user.id, role=user.role)

    return LoginResponse(user = user_info, access_token=token, token_type="Bearer")
    

@router.post("/register", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def register(dtos: UserRegisterDTOS, service: UserService = Depends(get_user_service)):
    try:
        await service.register(dtos)
        return
    except Exception as e:
        logger.error(f"Erro ao registrar user: {e}")
        raise HTTPException(status_code= 500, detail="Erro interno ao registrar usuário")


@router.post("/register/local_user", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def register_local_user(dtos: CreateLocalUserDTO, 
                              service: LocalUserService = Depends(get_local_user_service), 
                              current_user: UserDomain = Depends(get_current_user)):
    if current_user.role != Roles.ADMIN.value:
        raise HTTPException(status_code=403, detail="Usuário não autorizado")
    try:
        await service.create_user(dtos)
        return
    except Exception as e:
        logger.error(f"Erro ao registrar user: {e}")
        raise HTTPException(status_code= 500, detail="Erro interno ao registrar usuário")