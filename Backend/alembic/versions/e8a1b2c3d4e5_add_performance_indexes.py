"""add performance indexes

Revision ID: e8a1b2c3d4e5
Revises: d8e9f0a1b2c3
Create Date: 2026-09-06 20:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create performance indexes."""
    op.create_index('ix_users_is_admin_is_verified', 'users', ['is_admin', 'is_verified'], unique=False)
    op.create_index('ix_users_created_at', 'users', ['created_at'], unique=False)
    op.create_index('ix_contracts_user_created_at', 'contracts', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_contracts_status_created_at', 'contracts', ['status', 'created_at'], unique=False)
    op.create_index('ix_contract_analyses_risk_score', 'contract_analyses', ['risk_score'], unique=False)
    op.create_index('ix_contract_analyses_created_at', 'contract_analyses', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop performance indexes."""
    op.drop_index('ix_contract_analyses_created_at', table_name='contract_analyses')
    op.drop_index('ix_contract_analyses_risk_score', table_name='contract_analyses')
    op.drop_index('ix_contracts_status_created_at', table_name='contracts')
    op.drop_index('ix_contracts_user_created_at', table_name='contracts')
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_users_is_admin_is_verified', table_name='users')
