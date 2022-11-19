"""addes max_price to rooms

Revision ID: 8628c0d6cc83
Revises: a230c41a27f7
Create Date: 2022-11-19 11:49:47.159827

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8628c0d6cc83'
down_revision = 'a230c41a27f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('rooms', sa.Column('max_price', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('rooms', 'max_price')
    # ### end Alembic commands ###
