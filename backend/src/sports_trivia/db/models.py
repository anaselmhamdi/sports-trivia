"""SQLAlchemy models for Sports Trivia database.

Uses SQLAlchemy 2.0 style with type annotations and mapped_column.
"""

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class League(Base):
    """Reference table for sports/leagues (NBA, Soccer, etc.)."""

    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    slug: Mapped[str] = mapped_column(String(20), unique=True)

    # Relationships
    clubs: Mapped[list["Club"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<League(name='{self.name}', slug='{self.slug}')>"


class Club(Base):
    """Clubs/Teams table."""

    __tablename__ = "clubs"
    __table_args__ = (
        UniqueConstraint("league_id", "key", name="uq_clubs_league_key"),
        Index("idx_clubs_league_key", "league_id", "key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    external_id: Mapped[int | None] = mapped_column()
    key: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(200))
    nickname: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    abbreviation: Mapped[str | None] = mapped_column(String(10))
    # Comma-separated alternate names from data source (e.g., "PSG, Paris Saint-Germain")
    alternate_names: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(100))
    logo: Mapped[str | None] = mapped_column(String(500))
    logo_small: Mapped[str | None] = mapped_column(String(500))
    badge: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    league: Mapped["League"] = relationship(back_populates="clubs")
    players: Mapped[list["Player"]] = relationship(
        secondary="club_players",
        back_populates="clubs",
    )
    aliases: Mapped[list["ClubAlias"]] = relationship(
        back_populates="club",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Club(full_name='{self.full_name}', key='{self.key}')>"


class Player(Base):
    """Players table (normalized - each player appears once)."""

    __tablename__ = "players"
    __table_args__ = (Index("idx_players_normalized", "name_normalized"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_normalized: Mapped[str] = mapped_column(String(200))

    # Future-proof fields for player images
    external_id: Mapped[str | None] = mapped_column(String(100))  # League-specific ID
    image_url: Mapped[str | None] = mapped_column(String(500))  # Direct URL or None

    # Relationships
    clubs: Mapped[list["Club"]] = relationship(
        secondary="club_players",
        back_populates="players",
    )

    def __repr__(self) -> str:
        return f"<Player(name='{self.name}')>"


class ClubPlayer(Base):
    """Many-to-many association: players who played for clubs."""

    __tablename__ = "club_players"
    __table_args__ = (
        Index("idx_club_players_club", "club_id"),
        Index("idx_club_players_player", "player_id"),
    )

    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)


class ClubAlias(Base):
    """Club name aliases for flexible lookups.

    Aliases are league-scoped, so 'spurs' can map to both
    San Antonio Spurs (NBA) and Tottenham Hotspur (Soccer).
    """

    __tablename__ = "club_aliases"
    __table_args__ = (
        # League-scoped uniqueness: same alias can exist in different leagues
        UniqueConstraint("league_id", "alias_normalized", name="uq_aliases_league_alias"),
        Index("idx_aliases_league_normalized", "league_id", "alias_normalized"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    alias: Mapped[str] = mapped_column(String(200))
    alias_normalized: Mapped[str] = mapped_column(String(200))

    # Relationships
    club: Mapped["Club"] = relationship(back_populates="aliases")
    league: Mapped["League"] = relationship()

    def __repr__(self) -> str:
        return f"<ClubAlias(alias='{self.alias}')>"
