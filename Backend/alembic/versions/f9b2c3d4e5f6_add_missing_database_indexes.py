"""add missing database indexes

Revision ID: f9b2c3d4e5f6
Revises: e8a1b2c3d4e5
Create Date: 2026-09-06 21:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e8a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create missing indexes."""
    op.create_index('ix_users_is_admin', 'users', ['is_admin'], unique=False)
    op.create_index('ix_users_is_verified', 'users', ['is_verified'], unique=False)
    op.create_index('ix_users_updated_at', 'users', ['updated_at'], unique=False)
    op.create_index('ix_contracts_status', 'contracts', ['status'], unique=False)
    op.create_index('ix_contracts_created_at', 'contracts', ['created_at'], unique=False)
    op.create_index('ix_contracts_original_filename', 'contracts', ['original_filename'], unique=False)
    op.create_index('ix_contract_analyses_analysis_version', 'contract_analyses', ['analysis_version'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop missing indexes."""
    op.drop_index('ix_contract_analyses_analysis_version', table_name='contract_analyses')
    op.drop_index('ix_contracts_original_filename', table_name='contracts')
    op.drop_index('ix_contracts_created_at', table_name='contracts')
    op.drop_index('ix_contracts_status', table_name='contracts')
    op.drop_index('ix_users_updated_at', table_name='users')
    op.drop_index('ix_users_is_verified', table_name='users')
    op.drop_index('ix_users_is_admin', table_name='users')
