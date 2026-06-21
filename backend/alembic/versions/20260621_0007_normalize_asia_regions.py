"""normalize Asia regions

Revision ID: 20260621_0007
Revises: 20260621_0006
Create Date: 2026-06-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260621_0007"
down_revision: str | None = "20260621_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASIA_EX_JAPAN_COUNTRIES = (
    ("Bangladesh", ("BD", "BANGLADESH")),
    ("China", ("CN", "CHINA")),
    ("Hong Kong", ("HK", "HONG KONG")),
    ("India", ("IN", "INDIA")),
    ("Indonesia", ("ID", "INDONESIA")),
    ("Malaysia", ("MY", "MALAYSIA")),
    ("Pakistan", ("PK", "PAKISTAN")),
    ("Philippines", ("PH", "PHILIPPINES")),
    ("Singapore", ("SG", "SINGAPORE")),
    ("South Korea", ("KR", "SOUTH KOREA", "KOREA")),
    ("Taiwan", ("TW", "TAIWAN")),
    ("Thailand", ("TH", "THAILAND")),
    ("Vietnam", ("VN", "VIETNAM")),
)


def update_country_region(
    canonical_country: str,
    region: str,
    aliases: tuple[str, ...],
) -> None:
    quoted_aliases = ", ".join(f"'{alias}'" for alias in aliases)
    op.execute(
        sa.text(
            f"""
            UPDATE instruments
            SET country = :country, region = :region
            WHERE UPPER(country) IN ({quoted_aliases})
            """
        ).bindparams(country=canonical_country, region=region)
    )


def upgrade() -> None:
    for country, aliases in ASIA_EX_JAPAN_COUNTRIES:
        update_country_region(country, "Asia ex-Japan", aliases)

    update_country_region("Japan", "Japan", ("JP", "JAPAN"))
    update_country_region("Australia", "Asia Pacific", ("AU", "AUSTRALIA"))
    update_country_region("New Zealand", "Asia Pacific", ("NZ", "NEW ZEALAND"))

    op.execute(
        sa.text(
            """
            UPDATE instruments
            SET country = NULL, region = 'Asia ex-Japan'
            WHERE UPPER(asset_class) = 'ETF'
              AND (
                LOWER(name) LIKE '%asia%ex%japan%'
                OR LOWER(name) LIKE '%pacific%ex%japan%'
              )
            """
        )
    )


def downgrade() -> None:
    pass
