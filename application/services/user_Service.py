from domain.entities.user import User, Roles
from application.providers.hash import HashProvider
from application.providers.repo import UserRepo, UOWProvider
from application.dtos import user
from uuid import UUID

class Conflict(Exception):
    pass

class UserService():
    def __init__(self, user_repo: UserRepo, hash_provider: HashProvider, uow: UOWProvider):
        self.user_repo = user_repo
        self.hash_provider = hash_provider
        self.uow = uow

    async def register(self, dto: user.UserRegisterDTOS):
        if await self.user_repo.get_by_email(dto.email):
            raise Conflict("User already exists")
        User.validate_password_strenght(dto.senha)
        hashed = self.hash_provider.hash(dto.senha)
        new = User(name=dto.nome, email=dto.email, senha_hash=hashed, role=Roles.CLIENTE)
        await self.user_repo.save(new)
        await self.uow.commit()
        return
    
    async def can_login(self, dto: user.LoginDTOS) -> bool:
        user = await self.user_repo.get_by_email(dto.email)
        return self.hash_provider.verify(user.senha_hash, dto.senha)
    
    async def update_senha(self, user_id: UUID, new_password: str):
        user = await self.user_repo.get_by_id(user_id)
        user.validate_password_strenght(new_password)
        hashed = self.hash_provider.hash(new_password)
        user.senha_hash = hashed
        await self.user_repo.save(user)
        await self.uow.commit()
        return
    