import pytest

from application.services.user_Service import UserService
from domain.entities.user import Roles, User


class RecordingUserRepository:
    def __init__(self):
        self.saved_users = []

    async def save(self, user):
        self.saved_users.append(user)


class RecordingHashProvider:
    def hash(self, password):
        return f"hashed:{password}"


class RecordingUnitOfWork:
    def __init__(self):
        self.commit_calls = 0

    async def commit(self):
        self.commit_calls += 1


@pytest.mark.asyncio
async def test_user_service_updates_an_existing_users_password():
    repository = RecordingUserRepository()
    unit_of_work = RecordingUnitOfWork()
    user = User(
        name="User",
        email="user@example.com",
        senha_hash="old-hash",
        role=Roles.CLIENTE,
    )
    service = UserService(repository, RecordingHashProvider(), unit_of_work)

    await service.update_senha(user, "new-password")

    assert user.senha_hash == "hashed:new-password"
    assert repository.saved_users == [user]
    assert unit_of_work.commit_calls == 1
