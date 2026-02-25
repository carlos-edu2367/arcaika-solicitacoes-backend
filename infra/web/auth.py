from fastapi import Depends, HTTPException
from infra.db.setup import get_db, AsyncSession
from infra.db.repos import UserRepositoryINFRA, UserDomain
from infra.providers import TokenProvider
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

token_provider = TokenProvider()

async def get_user_repo(
    session: AsyncSession = Depends(get_db),
) -> UserRepositoryINFRA:
    return UserRepositoryINFRA(session)

security_scheme = HTTPBearer()

async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security_scheme),
    repo: UserRepositoryINFRA = Depends(get_user_repo),
) -> UserDomain:

    token = auth.credentials 
    
    try:
        payload = token_provider.get_payload(token)
        
        user = await repo.get_by_id(payload.id)

        if not user:
            raise HTTPException(
                status_code=401, 
                detail="Usuário não encontrado"
            )

        return user

    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail="Credenciais inválidas ou expiradas"
        )