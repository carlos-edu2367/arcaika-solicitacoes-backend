import pytest
from fastapi import HTTPException

from application.dtos.user import ChangePassword, LoginRole
from infra.web.routes.user import change_password


class MissingUserRepository:
    def __init__(self):
        self.get_calls = []

    async def get_by_email(self, email):
        self.get_calls.append(email)
        return None


class PasswordHasher:
    def verify(self, password_hash, password):
        return False


class UserServiceWithMissingUser:
    def __init__(self):
        self.user_repo = MissingUserRepository()
        self.hash_provider = PasswordHasher()
        self.update_calls = []

    async def update_senha(self, user, new_password):
        self.update_calls.append((user, new_password))


class LocalUserServiceWithMissingUser:
    def __init__(self):
        self.local_user_repo = MissingUserRepository()
        self.hash = PasswordHasher()
        self.update_calls = []

    async def update_senha(self, user, new_password):
        self.update_calls.append((user, new_password))


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [LoginRole.CLIENTE, LoginRole.LOCAL_USER])
async def test_change_password_rejects_an_unknown_account(role):
    user_service = UserServiceWithMissingUser()
    local_user_service = LocalUserServiceWithMissingUser()
    dto = ChangePassword(
        email="missing@example.com",
        role=role,
        old_password="old-password",
        new_password="new-password",
    )

    with pytest.raises(HTTPException) as error:
        await change_password(dto, local_user_service, user_service)

    assert error.value.status_code == 400
    assert error.value.detail == "Senha incorreta"
    assert user_service.update_calls == []
    assert local_user_service.update_calls == []
    assert user_service.user_repo.get_calls == (
        ["missing@example.com"] if role == LoginRole.CLIENTE else []
    )
    assert local_user_service.local_user_repo.get_calls == (
        [] if role == LoginRole.CLIENTE else ["missing@example.com"]
    )
