from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.entities.user import Roles, User
from infra.db.repos import UserRepositoryINFRA


class QueryResult:
    def __init__(self, user):
        self.user = user

    def scalar_one_or_none(self):
        return self.user


class SessionWithExistingUser:
    def __init__(self, user):
        self.user = user
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return QueryResult(self.user)


@pytest.mark.asyncio
async def test_user_repository_updates_an_existing_user_by_its_id():
    user_id = uuid4()
    stored_user = SimpleNamespace(
        name="Old name",
        email="old@example.com",
        role=Roles.CLIENTE.value,
        senha_hash="old-hash",
    )
    session = SessionWithExistingUser(stored_user)
    user = User(
        id=user_id,
        name="New name",
        email="new@example.com",
        role=Roles.ADMIN,
        senha_hash="new-hash",
    )

    await UserRepositoryINFRA(session).save(user)

    assert len(session.statements) == 1
    assert user_id in session.statements[0].compile().params.values()
    assert stored_user.name == "New name"
    assert stored_user.email == "new@example.com"
    assert stored_user.role == Roles.ADMIN
    assert stored_user.senha_hash == "new-hash"
