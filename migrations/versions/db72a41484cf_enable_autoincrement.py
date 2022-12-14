"""enable autoincrement

Revision ID: db72a41484cf
Revises: 16f95e352543
Create Date: 2022-11-17 19:29:34.817810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db72a41484cf'
down_revision = '16f95e352543'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("rooms", "id", autoincrement=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("rooms", "id", autoincrement=False)
    # ### end Alembic commands ###
