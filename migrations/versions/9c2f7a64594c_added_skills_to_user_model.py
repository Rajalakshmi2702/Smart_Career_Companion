"""Added skills to user model

Revision ID: 9c2f7a64594c
Revises: b84f19d7c4d1
Create Date: 2025-02-05 22:10:39.738412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c2f7a64594c'
down_revision = 'b84f19d7c4d1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        op.add_column('user', sa.Column('skills', sa.String(150), nullable=False, server_default=''))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('skills')

    # ### end Alembic commands ###
