"""add is_admin to users

Revision ID: a8d9e7f6c5b4
Revises: fdc061cf80f4
Create Date: 2026-08-11 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d9e7f6c5b4'
down_revision: Union[str, Sequence[str], None] = 'fdc061cf80f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
