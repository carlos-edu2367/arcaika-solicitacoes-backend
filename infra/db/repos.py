from application.providers import repo
from domain.entities.user import User as UserDomain, Roles
from domain.entities.locais import Local as LocalDomain
from domain.entities.solicitacao import Solicitacao as SolicitacaoDomain, Status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from infra.db.models import User as UserORM, Local as LocalORM, Solicitacao as SolicitacaoORM, AnexoSolicitacao
from fastapi import HTTPException, UploadFile
from application.dtos.solicitacao import SolicitacaoDisplay, AnexosDisplay, LocalResponse
from infra.providers import StorageProvider
from typing import List, Tuple

class UserRepositoryINFRA(repo.UserRepo):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> UserDomain | None:
        stmt = select(UserORM).where(UserORM.email == email)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None
        return user.to_domain()


    async def get_by_id(self, id: UUID) -> UserDomain:
        stmt = select(UserORM).where(UserORM.id == id)
        result = await self.session.execute(stmt)
        user_orm = result.scalar_one_or_none()
        if not user_orm:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        return user_orm.to_domain()
    
    async def get_admins(self) -> List[tuple[str, str]]:
        stmt = (
            select(UserORM.name, UserORM.email)
            .where(UserORM.role == Roles.ADMIN.value)
        )

        result = await self.session.execute(stmt)
        admins = result.all()  # já vem como lista de tuplas

        return [(nome, email) for nome, email in admins]
    
    async def save(self, user: UserDomain):
        if not user.id:
            user_orm = UserORM(name = user.name, 
                               email= user.email, 
                               senha_hash = user.senha_hash, 
                               role = user.role.value)
            self.session.add(user_orm)
            return
        
        stmt = select(UserORM).where(UserORM.id == id)
        result = await self.session.execute(stmt)
        user_orm = result.scalar_one_or_none()
        if not user_orm:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        user_orm.name = user.name
        user_orm.email = user.email
        user_orm.role = user.role
        user_orm.senha_hash = user.senha_hash
        return
    

class LocalRepositoryINFRA(repo.LocalRepo):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> LocalDomain:
        stmt = select(LocalORM).where(LocalORM.id == id)
        result = await self.session.execute(stmt)
        local = result.scalar_one_or_none()
        if not local:
            raise HTTPException(status_code=404, detail="Local não encontrado")
        return local.to_domain()

    async def get_by_city(self, city: str, state: str) -> list[LocalResponse] | None:
        stmt = select(LocalORM).where(LocalORM.cidade == city.upper(), 
                                      LocalORM.estado == state.upper())
        result = await self.session.execute(stmt)
        locais = result.scalars().all()
        response = []
        for local in locais:
            response.append(LocalResponse(id=local.id, nome=local.nome, estado=local.estado, cidade=local.cidade))
        return response

    async def save(self, local: LocalDomain):

        if not local.id:
            new = LocalORM(nome = local.nome.upper(),
                           cidade = local.cidade.upper(),
                           estado = local.estado.upper())
            self.session.add(new)
            return
        
        stmt = select(LocalORM).where(LocalORM.id == local.id)
        result = await self.session.execute(stmt)
        loc = result.scalar_one_or_none()
        if not loc:
            raise HTTPException(status_code=404, detail="Local não encontrado")
        loc.cidade = local.cidade.upper()
        loc.estado = local.estado.upper()
        loc.nome = local.nome.upper()
        return
    
class SolicitacaoRepositoryINFRA(repo.SolicitacaoRepo):

    def __init__(self, session: AsyncSession):
        self.session = session
        self.storage = StorageProvider()

    async def get_by_id(self, id: UUID) -> SolicitacaoDomain:
        stmt = select(SolicitacaoORM).where(SolicitacaoORM.id == id)
        result = await self.session.execute(stmt)
        solicitacao = result.scalar_one_or_none()
        if not solicitacao:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        return solicitacao.to_domain
    
    async def get_by_id_for_user(self, id: UUID) -> SolicitacaoDisplay:
        stmt = select(SolicitacaoORM).where(SolicitacaoORM.id == id).options(joinedload(SolicitacaoORM.anexos))
        result = await self.session.execute(stmt)
        solicitacao = result.unique().scalar_one_or_none()
        if not solicitacao:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        response = SolicitacaoDisplay(
            id=solicitacao.id,
            local_id=solicitacao.local_id,
            assunto=solicitacao.assunto,
            nome=solicitacao.nome,
            email=solicitacao.email,
            telefone=solicitacao.telefone,
            descricao=solicitacao.descricao,
            prioridade=solicitacao.prioridade,
            nome_da_unidade = solicitacao.nome_da_unidade,
            ordem_de_servico= solicitacao.ordem_servico,
            informacoes_adicionais=solicitacao.informacoes_adicionais,
            anexos=[]
        )
        if solicitacao.anexos:
            for anexo in solicitacao.anexos:
                url = await self.storage.get_by_path(anexo.file_path)
                new = AnexosDisplay(id=anexo.id, title=anexo.title, url=url)
                response.anexos.append(new)
        return response

    async def get_by_local_id(
    self,
    local_id: UUID,
    limit: int = 10,
    offset: int = 0
    ) -> list[SolicitacaoDisplay]:

        stmt = (
            select(SolicitacaoORM)
            .where(SolicitacaoORM.local_id == local_id)
            .order_by(SolicitacaoORM.created_date.desc())  
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        solicitacoes = result.scalars().all()

        return [
            SolicitacaoDisplay(
                id=s.id,
                local_id=s.local_id,
                assunto=s.assunto,
                nome=s.nome,
                email=s.email,
                telefone=s.telefone,
                descricao=s.descricao,
                prioridade=s.prioridade,
                nome_da_unidade = s.nome_da_unidade,
                ordem_de_servico = s.ordem_servico,
                informacoes_adicionais=s.informacoes_adicionais,
            )
            for s in solicitacoes
        ]
    
    async def get_by_status(self, status: Status, limit: int = 10,
                            offset: int = 0) -> list[SolicitacaoDisplay]:
        stmt = (
            select(SolicitacaoORM)
            .where(SolicitacaoORM.status == status.value)
            .order_by(SolicitacaoORM.created_date.desc())  
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        solicitacoes = result.scalars().all()

        return [
            SolicitacaoDisplay(
                id=s.id,
                local_id=s.local_id,
                assunto=s.assunto,
                nome=s.nome,
                email=s.email,
                telefone=s.telefone,
                descricao=s.descricao,
                prioridade=s.prioridade,
                nome_da_unidade = s.nome_da_unidade,
                ordem_de_servico = s.ordem_servico,
                informacoes_adicionais=s.informacoes_adicionais,
            )
            for s in solicitacoes
        ]

    async def save(self, solicitacao: SolicitacaoDomain) -> SolicitacaoDomain:
        if not solicitacao.id:
            new = SolicitacaoORM(local_id = solicitacao.local.id,
                                 nome = solicitacao.nome.upper(),
                                 assunto = solicitacao.assunto.upper(),
                                 email = solicitacao.email,
                                 telefone = solicitacao.telefone,
                                 descricao = solicitacao.descricao,
                                 prioridade = solicitacao.prioridade.value,
                                 informacoes_adicionais = solicitacao.informacoes_adicionais,
                                 status = solicitacao.status.value,
                                 nome_da_unidade = solicitacao.nome_da_unidade.upper())
            self.session.add(new)
            await self.session.flush()
            await self.session.refresh(new, ["local"]) 
        
            return new.to_domain()
        
        stmt = select(SolicitacaoORM).where(SolicitacaoORM.id == solicitacao.id)
        result = await self.session.execute(stmt)
        solic = result.scalar_one_or_none()
        if not solic:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        
        solic.local_id = solicitacao.local.id
        solic.nome = solicitacao.nome.upper()
        solic.email = solicitacao.email
        solic.assunto = solicitacao.assunto.upper()
        solic.telefone = solicitacao.telefone
        solic.prioridade = solicitacao.prioridade.value
        solic.informacoes_adicionais = solicitacao.informacoes_adicionais
        solic.status = solicitacao.status.value
        solic.nome_da_unidade = solicitacao.nome_da_unidade.upper()
        await self.session.flush()
        await self.session.refresh(solic, ["local"])
        return solic.to_domain()
    
    async def add_anexo(self, solicitacao_id: UUID, files: list[UploadFile]) -> list[AnexosDisplay]:
        solicitacao = await self.session.get(SolicitacaoORM, solicitacao_id)
        if not solicitacao:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")
        
        response = []
        
        for file in files:
            try:
                path = await self.storage.upload_file(file)
                new = AnexoSolicitacao(title = file.filename, file_path = path, solicitacao_id= solicitacao.id)
                self.session.add(new)
                await self.session.flush()
                signated_url = await self.storage.get_by_path(path)
                response.append(AnexosDisplay(id=new.id, title=new.title, url=signated_url))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erro ao anexar documentos: {e}")
            
        await self.session.commit()
        return response
    

class UOWProviderINFRA(repo.UOWProvider):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()