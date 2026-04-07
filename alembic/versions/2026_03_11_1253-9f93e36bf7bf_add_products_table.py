"""add products table

Revision ID: 9f93e36bf7bf
Revises: 91a92d86a3a2
Create Date: 2026-03-11 12:53:26.194784

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9f93e36bf7bf'
down_revision: Union[str, None] = '91a92d86a3a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем таблицу чистым SQL
    op.execute("""
        CREATE TABLE products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            price NUMERIC(10, 2) NOT NULL,
            owner_username VARCHAR(255) NOT NULL
        );
    """)

def downgrade() -> None:
    # Удаляем таблицу при откате
    op.execute("DROP TABLE products;")