"""add database indexes

Revision ID: d8e9f0a1b2c3
Revises: fdc061cf80f4
Create Date: 2026-09-06 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'a9497d098821'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_contracts_user_id_is_deleted', 'contracts', ['user_id', 'is_deleted'], unique=False)
    op.create_index('ix_contracts_status_is_deleted', 'contracts', ['status', 'is_deleted'], unique=False)
    op.create_index('ix_contract_analyses_contract_version', 'contract_analyses', ['contract_id', 'analysis_version'], unique=False)
    op.create_index('ix_contract_analyses_risk_level', 'contract_analyses', ['risk_level'], unique=False)
    op.create_index('ix_users_is_active', 'users', ['is_active'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_contract_analyses_risk_level', table_name='contract_analyses')
    op.drop_index('ix_contract_analyses_contract_version', table_name='contract_analyses')
    op.drop_index('ix_contracts_status_is_deleted', table_name='contracts')
    op.drop_index('ix_contracts_user_id_is_deleted', table_name='contracts')
