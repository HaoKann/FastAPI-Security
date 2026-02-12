"""Init db

Revision ID: 91a92d86a3a2
Revises: 
Create Date: 2026-02-12 06:10:36.140748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91a92d86a3a2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Создаем таблицу users сразу со всеми полями
    op.create_table(
        'users',
        sa.Column('username', sa.String(), primary_key=True, nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('avatar_url', sa.String(), nullable=True) # <-- Вот наша колонка
    )

def downgrade() -> None:
    op.drop_table('users')