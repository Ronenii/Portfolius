"""fix ETF exposure metadata

Revision ID: 20260621_0006
Revises: 20260608_0005
Create Date: 2026-06-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260621_0006"
down_revision: str | None = "20260608_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE instruments
            SET country = 'India', region = 'Asia ex-Japan'
            WHERE symbol = 'INDA'
              AND region = 'North America'
              AND (country IS NULL OR country IN ('US', 'United States'))
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE instruments
            SET country = 'United States', region = 'North America'
            WHERE symbol = 'CSPX'
              AND region = 'Europe'
              AND country IN ('IE', 'Ireland')
            """
        )
    )


def downgrade() -> None:
    pass
