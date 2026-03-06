from domain.entities.locais import Local
from domain.entities.solicitacao import Solicitacao, Status
from application.providers.hash import HashProvider
from application.providers.repo import UserRepo, UOWProvider, SolicitacaoRepo, LocalRepo
from application.dtos import solicitacao
from uuid import UUID

class SolicitacaoService():
    def __init__(self, user_repo: UserRepo, 
                 uow: UOWProvider, 
                 solicitacao_repo: SolicitacaoRepo,
                 local_repo: LocalRepo):
        self.user_repo = user_repo
        self.uow = uow
        self.solicitacao_repo = solicitacao_repo
        self.local_repo = local_repo
    
    async def create_local(self, dto:solicitacao.CreateLocalDTO):
        new = Local(nome= dto.nome, cidade= dto.cidade, estado=dto.estado)
        await self.local_repo.save(new)
        await self.uow.commit()
        return
    
    async def create_solicitacao(self, dto: solicitacao.CreateSolicitacao) -> Solicitacao:
        local = await self.local_repo.get_by_id(dto.local_id)
        new = Solicitacao(local=local,
                          assunto=dto.assunto,
                          nome=dto.nome,
                          email=dto.email,
                          telefone=dto.telefone,
                          descricao=dto.descricao,
                          prioridade=dto.prioridade,
                          informacoes_adicionais=dto.informacoes_adicionais,
                          nome_da_unidade=dto.nome_unidade)
        new = await self.solicitacao_repo.save(new)
        await self.uow.commit()
        return new
    
    async def update_status(self, solicitacao_id: UUID, status: Status):
        solicitacao = await self.solicitacao_repo.get_by_id(solicitacao_id)
        solicitacao.status = status
        await self.solicitacao_repo.save(solicitacao)
        await self.uow.commit()
        return
    
    async def update_solicitacao(self, dtos: solicitacao.UpdateSolicitacaoDTO) -> Solicitacao:
        solicitacao = await self.solicitacao_repo.get_by_id(dtos.solicitacao_id)
        if dtos.assunto:
            solicitacao.assunto = dtos.assunto
            print(f"update: {dtos.assunto}")
        if dtos.descricao:
            solicitacao.descricao = dtos.descricao
            print(f"update: {dtos.descricao}")
        if dtos.nome:
            solicitacao.nome = dtos.nome
            print(f"update: {dtos.nome}")
        if dtos.email:
            solicitacao.email = dtos.email
            print(f"update: {dtos.email}")
        if dtos.telefone:
            solicitacao.telefone = dtos.telefone
            print(f"update: {dtos.telefone}")
        if dtos.prioridade:
            solicitacao.prioridade = dtos.prioridade
            print(f"update: {dtos.prioridade}")
        if dtos.nome_da_unidade:
            solicitacao.nome_da_unidade = dtos.nome_da_unidade
            print(f"update: {dtos.nome_da_unidade}")
        if dtos.informacoes_adicionais:
            solicitacao.informacoes_adicionais = dtos.informacoes_adicionais
            print(f"update: {dtos.informacoes_adicionais}")
        
        await self.solicitacao_repo.save(solicitacao)
        await self.uow.commit()
        return solicitacao
    
    async def delete_solicitacao(self, solicitacao: Solicitacao):
        solicitacao.delete()
        await self.solicitacao_repo.save(solicitacao)
        await self.uow.commit()
        return