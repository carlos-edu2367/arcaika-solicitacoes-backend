from fastapi import APIRouter, HTTPException, Depends
from application.dtos.user import LoginDTOS, LoginResponse, UserInfo, UserRegisterDTOS
from application.dtos.solicitacao import CreateLocalDTO
from infra.web.dependencies import get_solicitacao_service, SolicitacaoService, get_user_service, UserService
from infra.providers import TokenProvider
from infra.db.repos import UserDomain
from infra.web.auth import get_current_user
from domain.entities.user import Roles
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/user", tags=["User"])
token_provider = TokenProvider()

@router.post("/login", response_model=LoginResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def login(dtos: LoginDTOS, service: UserService = Depends(get_user_service)) -> LoginResponse:
    if not await service.can_login(dtos):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    user:UserDomain = await service.user_repo.get_by_email(dtos.email)
    token = token_provider.create_token(user_id=user.id, role=user.role)
    return LoginResponse(
        user=UserInfo(
            nome=user.name, email=user.email, role=user.role
        ),
        access_token=token,
        token_type="Bearer"
    )

@router.post("/register", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def register(dtos: UserRegisterDTOS, service: UserService = Depends(get_user_service)):
    try:
        await service.register(dtos)
        return
    except Exception as e:
        raise HTTPException(status_code= 500, detail="Erro interno ao registrar usuário")
 