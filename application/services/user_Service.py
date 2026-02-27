from domain.entities.user import User, Roles
from domain.entities.locais import LocalUser
from application.providers.hash import HashProvider
from application.providers.repo import UserRepo, UOWProvider, LocalUserRepo, LocalRepo
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
    
    async def can_login(self, dto: user.LoginDTOS) -> User:
        user = await self.user_repo.get_by_email(dto.email)
        if not user:
            return None
        if not self.hash_provider.verify(user.senha_hash, dto.senha):
            return None
        return user
    
    async def update_senha(self, user_id: UUID, new_password: str):
        user = await self.user_repo.get_by_id(user_id)
        user.validate_password_strenght(new_password)
        hashed = self.hash_provider.hash(new_password)
        user.senha_hash = hashed
        await self.user_repo.save(user)
        await self.uow.commit()
        return
    
class LocalUserService():
    def __init__(self, local_user_repo: LocalUserRepo, local_repo: LocalRepo, hash: HashProvider, uow: UOWProvider):
        self.local_user_repo = local_user_repo
        self.local_repo = local_repo
        self.hash = hash
        self.uow = uow
    
    async def create_user(self, dto: user.CreateLocalUserDTO):
        if await self.local_user_repo.get_by_email(dto.email):
            raise Conflict("User already exists")
        local = await self.local_repo.get_by_id(dto.local_id)
        LocalUser.ensure_password_strenght(dto.senha)
        hashed = self.hash.hash(dto.senha)
        new = LocalUser(nome=dto.nome, email=dto.email, senha_hash=hashed, local_id=local.id)
        await self.local_user_repo.save(new)
        await self.uow.commit()
        return
    
    async def can_login(self, dto: user.LoginDTOS) -> LocalUser | None:
        user = await self.local_user_repo.get_by_email(dto.email)
        if not user:
            return None
        if not self.hash.verify(user.senha_hash, dto.senha):
            return None
        return user
    
    async def update_senha(self, local_user_id: UUID, new_password: str):
        user = await self.local_user_repo.get_by_id(local_user_id)
        user.ensure_password_strenght(new_password)
        hashed = self.hash.hash(new_password)
        user.senha_hash = hashed
        await self.local_user_repo.save(user)
        await self.uow.commit()
        return