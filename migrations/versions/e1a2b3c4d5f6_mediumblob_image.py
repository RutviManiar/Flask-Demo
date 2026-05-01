"""Make Emp.image a MEDIUMBLOB

Revision ID: e1a2b3c4d5f6
Revises: c583168c6475
Create Date: 2026-03-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5f6'
down_revision = 'c583168c6475'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'mysql':
        op.execute('ALTER TABLE emp MODIFY image MEDIUMBLOB')
    else:
        op.alter_column(
            'emp',
            'image',
            type_=sa.LargeBinary(length=(2**24 - 1)),
            existing_type=sa.LargeBinary(),
            existing_nullable=True,
        )


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'mysql':
        op.execute('ALTER TABLE emp MODIFY image BLOB')
    else:
        op.alter_column(
            'emp',
            'image',
            type_=sa.LargeBinary(),
            existing_type=sa.LargeBinary(length=(2**24 - 1)),
            existing_nullable=True,
        )
