from uuid import UUID
from domain.errors import DomainError
from enum import Enum

class LocalRoles(Enum):
    LOCAL_USER = "local_user"

class Local():
    def __init__(self, nome: str, cidade: str, estado: str, id: UUID = None):
        self.nome = nome
        self.cidade = cidade
        self.estado = estado
        self.id = id

class LocalUser():
    def __init__(self, nome: str, 
                 email: str, 
                 senha_hash: str, 
                 local_id: UUID, 
                 id: UUID = None, 
                 role: LocalRoles = LocalRoles.LOCAL_USER.value):
        self.nome = nome
        self.email = email
        self.senha_hash = senha_hash
        self.local_id = local_id
        self.id = id
        self.role = role

    def ensure_password_strenght(password: str):
        if len(password) < 6:
            raise DomainError("Password is weak")