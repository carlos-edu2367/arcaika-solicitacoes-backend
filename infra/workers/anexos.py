import asyncio
import os
import logging
from typing import List

from infra.web.dependencies import (
    get_user_repo,
    get_uow,
    get_solicitacao_repo,
    get_local_repo
)

from application.services.solicitacao_service import SolicitacaoService
from infra.db.setup import AsyncSessionLocal


logger = logging.getLogger("worker.anexos")
logging.basicConfig(level=logging.INFO)


def processar_anexos_job(solicitacao_id: str, paths: List[str], classe: str):
    """
    Wrapper síncrono para RQ.
    """
    asyncio.run(_processar_anexos_job(solicitacao_id, paths, classe))


async def _processar_anexos_job(solicitacao_id: str, paths: List[str], classe: str):

    logger.info(f"Iniciando job anexos | solicitacao={solicitacao_id}")

    async with AsyncSessionLocal() as session:

        service = SolicitacaoService(
            user_repo=get_user_repo(session),
            uow=get_uow(session),
            solicitacao_repo=get_solicitacao_repo(session),
            local_repo=get_local_repo(session)
        )

        try:

            await service.solicitacao_repo.add_anexo(
                solicitacao_id=solicitacao_id,
                files=paths,
                classe=classe
            )

            await session.commit()

            logger.info(f"Upload concluído | solicitacao={solicitacao_id}")

        except Exception as e:

            await session.rollback()

            logger.exception(
                f"Erro ao processar anexos | solicitacao={solicitacao_id}"
            )

            raise e

        finally:

            for path in paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Arquivo temp removido: {path}")
                except Exception:
                    logger.warning(f"Falha ao remover arquivo temp: {path}")