from domain.entities.locais import Local
from domain.entities.solicitacao import Solicitacao
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
                          informacoes_adicionais=dto.informacoes_adicionais)
        new = await self.solicitacao_repo.save(new)
        await self.uow.commit()
        return new
    
    