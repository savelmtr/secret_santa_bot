"""addes passkey to rooms

Revision ID: 416538aa7d64
Revises: 378aa2ccd97e
Create Date: 2022-11-18 20:37:11.995856

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '416538aa7d64'
down_revision = '378aa2ccd97e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('rooms', sa.Column('passkey', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('rooms', 'passkey')
    # ### end Alembic commands ###