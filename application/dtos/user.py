from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from enum import Enum

class LoginRole(Enum):
    CLIENTE = "cliente"
    ADMIN = "admin"
    LOCAL_USER = "local_user"

class UserRegisterDTOS(BaseModel):
    nome: str
    email: EmailStr
    senha: str

class UserInfo(BaseModel):
    nome: str
    email: EmailStr
    role: LoginRole
    local_id: Optional[UUID] = None

class LoginDTOS(BaseModel):
    email: EmailStr
    senha: str

class LoginResponse(BaseModel):
    user: UserInfo
    access_token: str
    token_type: str

class CreateLocalUserDTO(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    local_id: UUID