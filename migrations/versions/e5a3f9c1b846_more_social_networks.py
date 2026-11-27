"""Allow the social networks the congress-legislators file now lists.

The publisher added eight networks to ``legislators-social-media.yaml`` (seen at commit
2b1fe728, 2026-11-22). The table keeps one row per member and network, so only the list of
allowed network names widens.

Revision ID: e5a3f9c1b846
Revises: c7e2b94d5a13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5a3f9c1b846"
down_revision: str | Sequence[str] | None = "c7e2b94d5a13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = ("twitter", "facebook", "instagram", "youtube", "mastodon")
_ADDED = ("threads", "bluesky", "substack", "linkedin", "tiktok", "medium", "rumble", "flickr")
_NAME = "person_social_account_network_check"


def _allow(networks: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{network}'" for network in networks)
    op.drop_constraint(_NAME, "person_social_account", schema="core", type_="check")
    op.create_check_constraint(
        _NAME, "person_social_account", f"network IN ({allowed})", schema="core"
    )


def upgrade() -> None:
    """Widen the allowed network names."""
    _allow(_BEFORE + _ADDED)


def downgrade() -> None:
    """Refuse to narrow the list while rows use an added network."""
    added = ", ".join(f"'{network}'" for network in _ADDED)
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM core.person_social_account WHERE network IN ({added})) THEN
                RAISE EXCEPTION 'refusing to discard social accounts on the added networks';
            END IF;
        END $$
        """
    )
    _allow(_BEFORE)
