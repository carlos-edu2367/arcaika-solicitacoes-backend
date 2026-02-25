from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegisterDTOS(BaseModel):
    nome: str
    email: EmailStr
    senha: str

class UserInfo(BaseModel):
    nome: str
    email: EmailStr
    role: str

class LoginDTOS(BaseModel):
    email: EmailStr
    senha: str

class LoginResponse(BaseModel):
    user: UserInfo
    access_token: str
    token_type: str