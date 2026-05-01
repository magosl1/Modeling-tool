"""Update UploadedFile for AI Document Manager

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to uploaded_files
    op.add_column('uploaded_files', sa.Column('entity_id', sa.String(length=36), nullable=True))
    op.add_column('uploaded_files', sa.Column('file_path', sa.String(length=500), nullable=True))
    op.add_column('uploaded_files', sa.Column('file_size_bytes', sa.Integer(), server_default='0', nullable=False))
    op.add_column('uploaded_files', sa.Column('is_ignored', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('uploaded_files', sa.Column('ai_analysis_json', sa.JSON(), nullable=True))
    op.add_column('uploaded_files', sa.Column('missing_inputs_json', sa.JSON(), nullable=True))
    
    # Make s3_key nullable
    op.alter_column('uploaded_files', 's3_key', existing_type=sa.String(length=500), nullable=True)
    
    # Create foreign key for entity_id
    op.create_foreign_key('fk_uploaded_files_entity_id', 'uploaded_files', 'entities', ['entity_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_uploaded_files_entity_id', 'uploaded_files', type_='foreignkey')
    op.alter_column('uploaded_files', 's3_key', existing_type=sa.String(length=500), nullable=False)
    op.drop_column('uploaded_files', 'missing_inputs_json')
    op.drop_column('uploaded_files', 'ai_analysis_json')
    op.drop_column('uploaded_files', 'is_ignored')
    op.drop_column('uploaded_files', 'file_size_bytes')
    op.drop_column('uploaded_files', 'file_path')
    op.drop_column('uploaded_files', 'entity_id')
