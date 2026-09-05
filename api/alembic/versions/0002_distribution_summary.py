"""player_distribution_summary

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_distribution_summary',
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('scoring_preset', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('floor_p10', sa.Float(), nullable=True),
        sa.Column('p25', sa.Float(), nullable=True),
        sa.Column('median_p50', sa.Float(), nullable=True),
        sa.Column('p75', sa.Float(), nullable=True),
        sa.Column('ceiling_p90', sa.Float(), nullable=True),
        sa.Column('mean', sa.Float(), nullable=True),
        sa.Column('std', sa.Float(), nullable=True),
        sa.Column('skewness', sa.Float(), nullable=True),
        sa.Column('histogram', sa.Text(), nullable=True),
        sa.Column('computed_points', sa.Float(), nullable=True),
        sa.Column('n_samples', sa.Integer(), nullable=True),
        sa.Column('source_projection_id', sa.Integer(), nullable=True),
        sa.Column('computed_at', sa.String(), nullable=False),
        sa.CheckConstraint(
            "scoring_preset IN ('standard','half_ppr','full_ppr')"),
        sa.CheckConstraint(
            "status IN ('ok','insufficient_history','unsupported_position')"),
        sa.ForeignKeyConstraint(['player_id'], ['player.mfl_id']),
        sa.ForeignKeyConstraint(['source_projection_id'],
                                ['player_projection.id']),
        sa.PrimaryKeyConstraint('player_id', 'scoring_preset'),
    )


def downgrade() -> None:
    op.drop_table('player_distribution_summary')
