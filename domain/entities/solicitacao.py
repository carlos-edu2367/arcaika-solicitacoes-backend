from enum import Enum
from uuid import UUID
from domain.entities.locais import Local

class Prioridade(Enum):
    BAIXA = "baixa"
    MEDIA = "média"
    ALTA = "alta"

class Status(Enum):
    CRIADO = "criado"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"

class Solicitacao():
    def __init__(self, local: Local, 
                 assunto: str, 
                 nome: str, 
                 email: str, 
                 telefone:str, 
                 descricao: str,
                 nome_da_unidade: str,
                 prioridade: Prioridade, 
                 status: Status = Status.CRIADO,
                 informacoes_adicionais: str = None, 
                 id: UUID = None,
                 ordem_servico: int = None):
        self.local = local
        self.assunto = assunto
        self.status = status
        self.nome = nome
        self.email = email
        self.telefone = telefone
        self.descricao = descricao
        self.prioridade = prioridade
        self.informacoes_adicionais = informacoes_adicionais
        self.id = id
        self.ordem_servico = ordem_servico
        self.nome_da_unidade = nome_da_unidade