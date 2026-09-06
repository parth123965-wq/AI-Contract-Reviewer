import pytest
from unittest.mock import AsyncMock, patch
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.contract import Contract
from app.schemas.user import UserCreate, UserLogin
from app.services.auth_service import AuthService, auth_service
from app.auth.password import hash_password

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def service():
    return AuthService()


@pytest.mark.asyncio
async def test_register_user_success(db_session: AsyncSession, service: AuthService):
    user_in = UserCreate(
        username="newuser",
        email="newuser@example.com",
        password="secretpassword123"
    )

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email:
        mock_gen_otp.return_value = "123456"

        created_user = await service.register_user(db=db_session, user=user_in)

        assert created_user.username == "newuser"
        assert created_user.email == "newuser@example.com"
        assert created_user.is_verified is False
        assert mock_gen_otp.called
        assert mock_send_email.called


@pytest.mark.asyncio
async def test_register_user_unverified_existing(db_session: AsyncSession, service: AuthService):
    # Existing unverified user
    unverified_user = User(
        username="olduser",
        email="unverified@example.com",
        password_hash=hash_password("oldpassword"),
        is_verified=False
    )
    db_session.add(unverified_user)
    await db_session.commit()

    user_in = UserCreate(
        username="updateduser",
        email="unverified@example.com",
        password="newpassword123"
    )

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email:
        mock_gen_otp.return_value = "654321"

        updated_user = await service.register_user(db=db_session, user=user_in)

        assert updated_user.username == "updateduser"
        assert updated_user.email == "unverified@example.com"
        assert updated_user.is_verified is False
        assert mock_gen_otp.called
        assert mock_send_email.called


@pytest.mark.asyncio
async def test_register_user_already_verified(db_session: AsyncSession, service: AuthService):
    verified_user = User(
        username="verifiedguy",
        email="verified@example.com",
        password_hash=hash_password("password123"),
        is_verified=True
    )
    db_session.add(verified_user)
    await db_session.commit()

    user_in = UserCreate(
        username="verifiedguy",
        email="verified@example.com",
        password="password123"
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.register_user(db=db_session, user=user_in)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Email already registered"


@pytest.mark.asyncio
async def test_verify_registration_success(db_session: AsyncSession, service: AuthService):
    unverified_user = User(
        username="toverify",
        email="toverify@example.com",
        password_hash=hash_password("password123"),
        is_verified=False
    )
    db_session.add(unverified_user)
    await db_session.commit()

    with patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify_otp:
        mock_verify_otp.return_value = True

        verified_user = await service.verify_registration(
            db=db_session,
            email="toverify@example.com",
            otp_code="123456"
        )

        assert verified_user.is_verified is True
        mock_verify_otp.assert_called_once_with(
            purpose="registration",
            identifier="toverify@example.com",
            input_otp="123456"
        )


@pytest.mark.asyncio
async def test_verify_registration_nonexistent_user(db_session: AsyncSession, service: AuthService):
    with pytest.raises(HTTPException) as exc_info:
        await service.verify_registration(db=db_session, email="nobody@example.com", otp_code="123456")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found."


@pytest.mark.asyncio
async def test_verify_registration_already_verified(db_session: AsyncSession, service: AuthService):
    verified_user = User(
        username="alreadyverified",
        email="alreadyverified@example.com",
        password_hash=hash_password("password123"),
        is_verified=True
    )
    db_session.add(verified_user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.verify_registration(db=db_session, email="alreadyverified@example.com", otp_code="123456")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "User is already verified."


@pytest.mark.asyncio
async def test_resend_registration_otp_success(db_session: AsyncSession, service: AuthService):
    unverified_user = User(
        username="resenduser",
        email="resend@example.com",
        password_hash=hash_password("password123"),
        is_verified=False
    )
    db_session.add(unverified_user)
    await db_session.commit()

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email:
        mock_gen_otp.return_value = "999888"

        await service.resend_registration_otp(db=db_session, email="resend@example.com")

        mock_gen_otp.assert_called_once_with(purpose="registration", identifier="resend@example.com")
        mock_send_email.assert_called_once_with(email="resend@example.com", otp_code="999888", purpose="registration")


@pytest.mark.asyncio
async def test_resend_registration_otp_nonexistent_user(db_session: AsyncSession, service: AuthService):
    with pytest.raises(HTTPException) as exc_info:
        await service.resend_registration_otp(db=db_session, email="nonexistent@example.com")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found."


@pytest.mark.asyncio
async def test_resend_registration_otp_already_verified(db_session: AsyncSession, service: AuthService):
    verified_user = User(
        username="verifiedresend",
        email="verifiedresend@example.com",
        password_hash=hash_password("password123"),
        is_verified=True
    )
    db_session.add(verified_user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.resend_registration_otp(db=db_session, email="verifiedresend@example.com")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "User is already verified."


@pytest.mark.asyncio
async def test_login_user_success(db_session: AsyncSession, service: AuthService):
    user = User(
        username="loginuser",
        email="login@example.com",
        password_hash=hash_password("mypassword123"),
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    login_in = UserLogin(email="login@example.com", password="mypassword123")
    response = await service.login_user(db=db_session, user=login_in)

    assert response.access_token is not None
    assert response.token_type == "bearer"
    assert response.user.email == "login@example.com"


@pytest.mark.asyncio
async def test_login_user_invalid_email(db_session: AsyncSession, service: AuthService):
    login_in = UserLogin(email="nonexistent@example.com", password="mypassword123")

    with pytest.raises(HTTPException) as exc_info:
        await service.login_user(db=db_session, user=login_in)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid Email and Password."


@pytest.mark.asyncio
async def test_login_user_invalid_password(db_session: AsyncSession, service: AuthService):
    user = User(
        username="loginuser",
        email="login@example.com",
        password_hash=hash_password("mypassword123"),
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    login_in = UserLogin(email="login@example.com", password="wrongpassword")

    with pytest.raises(HTTPException) as exc_info:
        await service.login_user(db=db_session, user=login_in)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid Email and Password."


@pytest.mark.asyncio
async def test_login_user_unverified(db_session: AsyncSession, service: AuthService):
    user = User(
        username="unverifiedlogin",
        email="unverifiedlogin@example.com",
        password_hash=hash_password("mypassword123"),
        is_verified=False
    )
    db_session.add(user)
    await db_session.commit()

    login_in = UserLogin(email="unverifiedlogin@example.com", password="mypassword123")

    with pytest.raises(HTTPException) as exc_info:
        await service.login_user(db=db_session, user=login_in)

    assert exc_info.value.status_code == 403
    assert "Email address is not verified" in exc_info.value.detail


def test_auth_service_factory():
    instance = auth_service()
    assert isinstance(instance, AuthService)
