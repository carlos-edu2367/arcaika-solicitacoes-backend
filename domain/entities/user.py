from enum import Enum
from uuid import UUID
from domain.errors import DomainError

class Roles(Enum):
    ADMIN = "admin"
    CLIENTE = "cliente"

class User():
    def __init__(self, name: str, email: str, senha_hash: str, role: Roles, id: UUID = None):
        self.name = name
        self.email = email
        self.senha_hash = senha_hash
        self.role = role
        self.id = id

    def validate_password_strenght(password: str):
        if len(password) < 6:
            return DomainError("Password is weak")
