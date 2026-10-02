from datetime import datetime, timezone

import pytest

from app.models.contract import Contract, ContractAnalysis, ContractStatus, RiskLevel
from app.models.user import User
from app.repositories.contract_repository import ContractRepository
from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_user_repository_gets_user_by_id_email_and_username(db_session):
    user = User(
        username="repo-user",
        email="repo@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    repository = UserRepository()
    assert await repository.get_user_by_id(db_session, user.id) is user
    assert await repository.get_user_by_email(db_session, user.email) is user
    assert await repository.get_user_by_username(db_session, user.username) is user
    assert await repository.get_user_by_id(db_session, 999) is None


@pytest.mark.asyncio
async def test_user_repository_search_pagination_and_counts(db_session):
    db_session.add_all(
        [
            User(username="alpha", email="alpha@example.com", password_hash="hash"),
            User(
                username="beta",
                email="beta@example.com",
                password_hash="hash",
                is_active=False,
            ),
            User(username="gamma", email="gamma@example.com", password_hash="hash"),
        ]
    )
    await db_session.commit()
    repository = UserRepository()

    results = await repository.get_all_users(
        db_session,
        skip=0,
        limit=1,
        search="example.com",
        is_active=True,
    )

    assert len(results) == 1
    assert results[0].username == "gamma"
    assert await repository.count_users(
        db_session,
        search="example.com",
        is_active=True,
    ) == 2


async def add_user_and_contract(db_session, user_id=1, filename="agreement.pdf"):
    user = User(
        id=user_id,
        username=f"user-{user_id}",
        email=f"user-{user_id}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        user_id=user.id,
        original_filename=filename,
        stored_filename=f"stored-{user_id}.pdf",
        file_path=f"/uploads/stored-{user_id}.pdf",
        file_size=100,
        content_type="application/pdf",
        status=ContractStatus.COMPLETED,
    )
    db_session.add(contract)
    await db_session.flush()
    return user, contract


@pytest.mark.asyncio
async def test_contract_repository_gets_contract_by_id_and_owner(db_session):
    user, contract = await add_user_and_contract(db_session)
    await db_session.commit()
    repository = ContractRepository()

    fetched = await repository.get_contract_by_id(
        db_session,
        contract.id,
        user_id=user.id,
    )

    assert fetched.id == contract.id
    assert fetched.user.id == user.id
    assert await repository.get_contract_by_id(
        db_session,
        contract.id,
        user_id=user.id + 1,
    ) is None


@pytest.mark.asyncio
async def test_contract_analysis_relationship_is_ordered_by_version_then_id(db_session):
    user, contract = await add_user_and_contract(db_session)
    db_session.add_all(
        [
            ContractAnalysis(
                contract_id=contract.id,
                analysis_version=2,
                summary="version two",
                risk_level=RiskLevel.MEDIUM,
            ),
            ContractAnalysis(
                contract_id=contract.id,
                analysis_version=1,
                summary="version one",
                risk_level=RiskLevel.LOW,
            ),
            ContractAnalysis(
                contract_id=contract.id,
                analysis_version=2,
                summary="version two duplicate",
                risk_level=RiskLevel.HIGH,
            ),
        ]
    )
    await db_session.commit()
    db_session.expire(contract, ["analyses"])

    fetched = await ContractRepository().get_contract_by_id(db_session, contract.id)

    assert [analysis.analysis_version for analysis in fetched.analyses] == [1, 2, 2]
    assert fetched.analyses[-1].summary == "version two duplicate"


@pytest.mark.asyncio
async def test_contract_repository_soft_delete_hides_contract(db_session):
    _, contract = await add_user_and_contract(db_session)
    await db_session.commit()
    repository = ContractRepository()

    await repository.soft_delete_contract(db_session, contract)

    assert await repository.get_contract_by_id(db_session, contract.id) is None
    assert contract.deleted_at is not None


@pytest.mark.asyncio
async def test_contract_repository_next_analysis_version(db_session):
    _, contract = await add_user_and_contract(db_session)
    repository = ContractRepository()
    assert await repository.get_next_analysis_version(db_session, contract.id) == 1

    db_session.add(
        ContractAnalysis(
            contract_id=contract.id,
            analysis_version=4,
            summary="latest",
        )
    )
    await db_session.commit()

    assert await repository.get_next_analysis_version(db_session, contract.id) == 5
