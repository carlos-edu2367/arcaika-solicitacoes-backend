from sqlalchemy import Column, String, ForeignKey, DateTime, func, Integer, Sequence
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from infra.db.setup import Base
from uuid import uuid4
from domain.entities.user import User as UserDomain
from domain.entities.solicitacao import Solicitacao as SolicitacaoDomain
from domain.entities.locais import Local as LocalDomain, LocalUser as LocalUserDomain

ordem_servico_seq = Sequence(
    "ordem_servico_seq",
    metadata=Base.metadata
)

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    senha_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)

    def to_domain(self) -> UserDomain:
        return UserDomain(name=self.name,
                          email=self.email,
                          senha_hash=self.senha_hash,
                          role=self.role,
                          id=self.id)

class Local(Base):
    __tablename__ = "locais"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    nome = Column(String, nullable=False)
    cidade = Column(String, nullable=False)
    estado = Column(String, nullable=False)

    solicitacoes = relationship("Solicitacao", back_populates="local", cascade="all, delete-orphan")

    def to_domain(self) -> LocalDomain:
        return LocalDomain(nome=self.nome,
                           cidade=self.cidade,
                           estado=self.estado,
                           id=self.id)

class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ordem_servico = Column(
        Integer,
        ordem_servico_seq,
        server_default=ordem_servico_seq.next_value(),
        unique=True,
        nullable=False
    )
    local_id = Column(UUID(as_uuid=True), ForeignKey("locais.id", ondelete="CASCADE"), nullable=False)
    nome_da_unidade = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    email = Column(String, nullable=False)
    assunto = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    prioridade = Column(String, nullable=False)
    informacoes_adicionais = Column(String, nullable=True)
    status = Column(String, nullable=False, default="criado")
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    local = relationship("Local", back_populates="solicitacoes")
    anexos = relationship("AnexoSolicitacao", back_populates="solicitacao", cascade="all, delete-orphan")

    def to_domain(self) -> SolicitacaoDomain:
        return SolicitacaoDomain(
            local=LocalDomain(nome=self.local.nome, cidade=self.local.cidade, estado=self.local.estado, id=self.local.id),
            assunto=self.assunto,
            nome=self.nome,
            email=self.email,
            telefone=self.telefone,
            descricao=self.descricao,
            prioridade=self.prioridade,
            status=self.status,
            informacoes_adicionais=self.informacoes_adicionais,
            id=self.id,
            ordem_servico=self.ordem_servico,
            nome_da_unidade=self.nome_da_unidade
        )
    
class AnexoSolicitacao(Base):
    __tablename__ = "anexos_solicitacao"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String, nullable=False)
    classe = Column(String, nullable=False, default="cliente") # "admin" quer dizer que o admin enviou
    file_path = Column(String, nullable=False)
    solicitacao_id = Column(UUID(as_uuid=True), ForeignKey("solicitacoes.id", ondelete="CASCADE"))

    solicitacao = relationship("Solicitacao", back_populates="anexos")

class LocalUser(Base):
    __tablename__ = "local_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    local_id = Column(UUID(as_uuid=True), ForeignKey("locais.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    senha_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="local_user")
    created_date = Column(DateTime(timezone=True), server_default=func.now())

    def to_domain(self) -> LocalUserDomain:
        return LocalUserDomain(nome=self.nome,
                               email=self.email,
                               senha_hash=self.senha_hash,
                               local_id=self.local_id,
                               id=self.id,
                               role=self.role)