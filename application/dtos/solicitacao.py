from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from domain.entities.solicitacao import Prioridade

class LocalResponse(BaseModel):
    id: UUID
    nome: str
    estado: str
    cidade: str

class CreateLocalDTO(BaseModel):
    nome: str
    cidade: str
    estado: str

class CreateSolicitacao(BaseModel):
    local_id: UUID
    assunto: str
    nome: str
    email: EmailStr
    telefone:str
    descricao: str
    prioridade: Prioridade
    informacoes_adicionais: Optional[str] = None

class AnexosDisplay(BaseModel):
    id: UUID
    title: str
    url: str

class SolicitacaoDisplay(BaseModel):
    id: UUID
    local_id: UUID
    assunto: str
    nome: str
    email: EmailStr
    telefone:str
    descricao: str
    prioridade: Prioridade
    informacoes_adicionais: Optional[str] = None
    anexos: Optional[list[AnexosDisplay]] = None