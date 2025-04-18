from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b84f19d7c4d1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add 'skills' column to the 'user' table
    op.add_column('user', sa.Column('skills', sa.String(length=150), nullable=False))

    # Create the 'resume' table (this part seems to be auto-generated)
    op.create_table('resume',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=15), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('skills', sa.Text(), nullable=True),
        sa.Column('experience', sa.Text(), nullable=True),
        sa.Column('education', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop 'resume' table
    op.drop_table('resume')

    # Drop 'skills' column from the 'user' table
    op.drop_column('user', 'skills')
