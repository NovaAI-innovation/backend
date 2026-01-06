"""add_display_order_to_gallery_images

Revision ID: f1f353154647
Revises: 473878844965
Create Date: 2026-01-06 16:07:56.993867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1f353154647'
down_revision: Union[str, None] = '473878844965'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add display_order column with default value 0
    op.add_column('gallery_images',
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0')
    )

    # Create index on display_order for efficient ordering
    op.create_index(
        op.f('ix_gallery_images_display_order'),
        'gallery_images',
        ['display_order'],
        unique=False
    )

    # Initialize display_order based on created_at (newest first = highest order number)
    # This ensures backward compatibility - existing images maintain their visual order
    op.execute("""
        UPDATE gallery_images
        SET display_order = subquery.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at DESC) as row_num
            FROM gallery_images
        ) as subquery
        WHERE gallery_images.id = subquery.id
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_gallery_images_display_order'), table_name='gallery_images')

    # Drop column
    op.drop_column('gallery_images', 'display_order')
