"""addes candidate_room_id to users

Revision ID: a230c41a27f7
Revises: 416538aa7d64
Create Date: 2022-11-18 21:24:51.052971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a230c41a27f7'
down_revision = '416538aa7d64'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('candidate_room_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'users', 'rooms', ['candidate_room_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_column('users', 'candidate_room_id')
    # ### end Alembic commands ###