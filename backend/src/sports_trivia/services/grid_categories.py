"""NBA Grid category system.

Each `GridCategory` represents one row or column header. A category is defined
by its family (team / award / draft / decade / stat / season_stat /
team_count / coach / birthplace) and carries a set of player IDs that match.

The registry is *data-driven*: each family builder queries the DB for whatever
data is available. Families whose source table is empty (e.g. awards before
the scraper has run) contribute nothing, so grids fall back gracefully.

Display names and descriptions are in English. The description is a one-line
clarification shown in the UI when a category needs disambiguation
(thresholds, era buckets, eligibility rules).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy.orm import Session

from sports_trivia.db import (
    Club,
    ClubPlayer,
    Coach,
    CoachPlayer,
    League,
    Player,
    PlayerAward,
    PlayerCareer,
    PlayerDraft,
    PlayerSeason,
)
from sports_trivia.models import GridCategory

# Minimum matching players for a category to be considered usable.
MIN_CATEGORY_PLAYERS = 10

# Until the real Basketball-Reference scraper has run, metadata families
# (awards, draft, decade, career/season stats, coaches, birthplace) are
# seeded with synthetic data that does NOT match real trivia knowledge.
# Keep this False while the metadata file has source="mock"; flip to True
# once real data lands so those categories re-enter the pool.
TRUST_METADATA_FAMILIES = False

# Marquee franchises shown in team categories. Exact DB keys.
MARQUEE_TEAM_KEYS: dict[str, tuple[str, str]] = {
    # key -> (display_label, icon_asset)
    "los angeles lakers": ("Lakers", "assets/category_icons/teams/lakers.png"),
    "boston celtics": ("Celtics", "assets/category_icons/teams/celtics.png"),
    "golden state warriors": ("Warriors", "assets/category_icons/teams/warriors.png"),
    "chicago bulls": ("Bulls", "assets/category_icons/teams/bulls.png"),
    "miami heat": ("Heat", "assets/category_icons/teams/heat.png"),
    "san antonio spurs": ("Spurs", "assets/category_icons/teams/spurs.png"),
    "new york knicks": ("Knicks", "assets/category_icons/teams/knicks.png"),
    "philadelphia 76ers": ("76ers", "assets/category_icons/teams/sixers.png"),
    "dallas mavericks": ("Mavericks", "assets/category_icons/teams/mavericks.png"),
    "houston rockets": ("Rockets", "assets/category_icons/teams/rockets.png"),
    "detroit pistons": ("Pistons", "assets/category_icons/teams/pistons.png"),
    "phoenix suns": ("Suns", "assets/category_icons/teams/suns.png"),
    "milwaukee bucks": ("Bucks", "assets/category_icons/teams/bucks.png"),
    "oklahoma city thunder": ("Thunder", "assets/category_icons/teams/thunder.png"),
    "denver nuggets": ("Nuggets", "assets/category_icons/teams/nuggets.png"),
    "toronto raptors": ("Raptors", "assets/category_icons/teams/raptors.png"),
    "brooklyn nets": ("Nets", "assets/category_icons/teams/nets.png"),
    "atlanta hawks": ("Hawks", "assets/category_icons/teams/hawks.png"),
    "portland trail blazers": ("Trail Blazers", "assets/category_icons/teams/blazers.png"),
    "cleveland cavaliers": ("Cavaliers", "assets/category_icons/teams/cavaliers.png"),
}

# Award family metadata — English label + icon asset.
_AWARD_META: dict[str, tuple[str, str]] = {
    "MVP": ("MVP", "assets/category_icons/awards/mvp.png"),
    "DPOY": ("Defensive Player of the Year", "assets/category_icons/awards/dpoy.png"),
    "ROY": ("Rookie of the Year", "assets/category_icons/awards/roy.png"),
    "6MOY": ("Sixth Man of the Year", "assets/category_icons/awards/6moy.png"),
    "FMVP": ("Finals MVP", "assets/category_icons/awards/fmvp.png"),
    "ALL_STAR": ("All-Star", "assets/category_icons/awards/all_star.png"),
    "ALL_NBA": ("All-NBA", "assets/category_icons/awards/all_nba.png"),
    "ALL_DEF": ("All-Defense", "assets/category_icons/awards/all_def.png"),
    "CHAMPION": ("NBA Champion", "assets/category_icons/awards/champion.png"),
}


def _unique(ids: Iterable[int]) -> list[int]:
    return sorted(set(ids))


# ---------- Teams ----------


def build_team_categories(session: Session) -> list[GridCategory]:
    """One category per marquee NBA franchise."""
    league = session.query(League).filter(League.slug == "nba").first()
    if league is None:
        return []

    out: list[GridCategory] = []
    clubs = session.query(Club).filter(Club.league_id == league.id).all()
    for club in clubs:
        meta = MARQUEE_TEAM_KEYS.get(club.key)
        if meta is None:
            continue
        label, icon_asset = meta
        player_ids = _unique(
            pid
            for (pid,) in session.query(ClubPlayer.player_id)
            .filter(ClubPlayer.club_id == club.id)
            .all()
        )
        if len(player_ids) < MIN_CATEGORY_PLAYERS:
            continue
        out.append(
            GridCategory(
                id=f"team_{club.key.replace(' ', '_')}",
                family="team",
                display_name=f"Played for the {label}",
                description=f"Appeared in at least one NBA game for the {club.full_name}.",
                icon_url=icon_asset or club.logo,
                icon_kind="logo",
                valid_player_ids=player_ids,
            )
        )
    return out


# ---------- Awards ----------


def build_award_categories(session: Session) -> list[GridCategory]:
    rows = session.query(PlayerAward.award_name, PlayerAward.player_id, PlayerAward.year).all()
    if not rows:
        return []

    by_award: dict[str, list[int]] = defaultdict(list)
    award_year_pairs: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for name, pid, year in rows:
        by_award[name].append(pid)
        if year is not None:
            award_year_pairs[name].append((pid, year))

    out: list[GridCategory] = []

    def _register(cid: str, name: str, description: str, icon: str, ids: list[int]) -> None:
        if len(ids) >= MIN_CATEGORY_PLAYERS:
            out.append(
                GridCategory(
                    id=cid,
                    family="award",
                    display_name=name,
                    description=description,
                    icon_url=icon,
                    icon_kind="trophy",
                    valid_player_ids=ids,
                )
            )

    for award_name, ids in by_award.items():
        display, icon = _AWARD_META.get(award_name, (award_name.title(), ""))
        unique_ids = _unique(ids)

        if award_name == "DPOY":
            _register(
                "award_dpoy",
                display,
                "Won Defensive Player of the Year at least once.",
                icon,
                unique_ids,
            )
        elif award_name == "ALL_NBA":
            _register(
                "award_all_nba_1x",
                "All-NBA (1x+)",
                "Selected to any All-NBA team at least once (First, Second, or Third).",
                icon,
                unique_ids,
            )
        elif award_name == "ALL_STAR":
            counts: dict[int, int] = defaultdict(int)
            for pid in ids:
                counts[pid] += 1
            qualified = _unique(pid for pid, c in counts.items() if c >= 3)
            _register(
                "award_all_star_3x",
                "3× All-Star",
                "Selected to at least three All-Star games in their career.",
                icon,
                qualified,
            )
        elif award_name == "ROY":
            _register(
                "award_roy",
                display,
                "Won Rookie of the Year.",
                icon,
                unique_ids,
            )
        elif award_name == "6MOY":
            _register(
                "award_6moy",
                display,
                "Won Sixth Man of the Year at least once.",
                icon,
                unique_ids,
            )
        elif award_name == "FMVP":
            _register(
                "award_fmvp",
                display,
                "Named Finals MVP at least once.",
                icon,
                unique_ids,
            )

    # Era variants
    mvp_pairs = award_year_pairs.get("MVP", [])
    if mvp_pairs:
        post_2010 = _unique(pid for pid, y in mvp_pairs if y >= 2010)
        _register(
            "award_mvp_since2010",
            "MVP since 2010",
            "Won regular-season MVP in 2010 or later.",
            _AWARD_META["MVP"][1],
            post_2010,
        )

    champ_pairs = award_year_pairs.get("CHAMPION", [])
    if champ_pairs:
        since_2015 = _unique(pid for pid, y in champ_pairs if y >= 2015)
        _register(
            "award_champion_since2015",
            "NBA Champion since 2015",
            "Won an NBA Championship in the 2014–15 season or later.",
            _AWARD_META["CHAMPION"][1],
            since_2015,
        )

    return out


# ---------- Draft ----------


def build_draft_categories(session: Session) -> list[GridCategory]:
    rows = session.query(PlayerDraft).all()
    if not rows:
        return []

    top1: list[int] = []
    top3: list[int] = []
    top5: list[int] = []
    lottery_top14: list[int] = []
    undrafted: list[int] = []
    for r in rows:
        if r.undrafted:
            undrafted.append(r.player_id)
            continue
        if r.overall_pick is None:
            continue
        if r.overall_pick == 1:
            top1.append(r.player_id)
        if r.overall_pick <= 3:
            top3.append(r.player_id)
        if r.overall_pick <= 5:
            top5.append(r.player_id)
        if 1 <= r.overall_pick <= 14:
            lottery_top14.append(r.player_id)

    default_icon = "assets/category_icons/draft/top1.png"
    buckets = [
        (
            "draft_top1",
            "#1 Overall Pick",
            "Drafted first overall in any NBA draft.",
            "assets/category_icons/draft/top1.png",
            top1,
        ),
        (
            "draft_top3",
            "Top 3 Pick",
            "Drafted with the #1, #2, or #3 overall pick.",
            default_icon,
            top3,
        ),
        (
            "draft_top5",
            "Top 5 Pick",
            "Drafted within the first five overall picks.",
            default_icon,
            top5,
        ),
        (
            "draft_lottery_top14",
            "Lottery Pick (Top 14)",
            "Drafted with a pick in the first 14 (current lottery range).",
            "assets/category_icons/draft/lottery.png",
            lottery_top14,
        ),
        (
            "draft_undrafted",
            "Undrafted",
            "Entered the NBA without being selected in any draft.",
            "assets/category_icons/draft/undrafted.png",
            undrafted,
        ),
    ]
    return [
        GridCategory(
            id=cid,
            family="draft",
            display_name=label,
            description=desc,
            icon_url=icon_path,
            icon_kind="trophy",
            valid_player_ids=_unique(ids),
        )
        for cid, label, desc, icon_path, ids in buckets
        if len(_unique(ids)) >= MIN_CATEGORY_PLAYERS
    ]


# ---------- Decade ----------


def build_decade_categories(session: Session) -> list[GridCategory]:
    rows = session.query(
        PlayerCareer.player_id, PlayerCareer.first_year, PlayerCareer.last_year
    ).all()
    if not rows:
        return []

    decades = {
        1970: "70s",
        1980: "80s",
        1990: "90s",
        2000: "2000s",
        2010: "2010s",
        2020: "2020s",
    }
    by_decade: dict[int, list[int]] = defaultdict(list)
    for pid, first, last in rows:
        if first is None or last is None:
            continue
        for d in decades:
            if first <= d + 9 and last >= d:
                by_decade[d].append(pid)

    return [
        GridCategory(
            id=f"decade_{d}",
            family="decade",
            display_name=f"Played in the {label}",
            description=f"Played at least one NBA season between {d} and {d + 9}.",
            icon_url=None,
            icon_kind="text",
            valid_player_ids=_unique(by_decade[d]),
        )
        for d, label in decades.items()
        if len(_unique(by_decade[d])) >= MIN_CATEGORY_PLAYERS
    ]


# ---------- Career stats ----------


def build_career_stat_categories(session: Session) -> list[GridCategory]:
    rows = session.query(PlayerCareer).all()
    if not rows:
        return []

    thresholds = [
        (
            "stat_career_ppg20",
            "20+ Career PPG",
            "Career scoring average of at least 20 points per game.",
            "career_ppg",
            20.0,
        ),
        (
            "stat_career_rpg10",
            "10+ Career RPG",
            "Career rebounding average of at least 10 per game.",
            "career_rpg",
            10.0,
        ),
        (
            "stat_career_apg8",
            "8+ Career APG",
            "Career assist average of at least 8 per game.",
            "career_apg",
            8.0,
        ),
    ]
    out: list[GridCategory] = []
    for cid, label, desc, attr, threshold in thresholds:
        ids = _unique(r.player_id for r in rows if (getattr(r, attr) or 0) >= threshold)
        if len(ids) >= MIN_CATEGORY_PLAYERS:
            out.append(
                GridCategory(
                    id=cid,
                    family="stat",
                    display_name=label,
                    description=desc,
                    icon_url=None,
                    icon_kind="text",
                    valid_player_ids=ids,
                )
            )
    return out


# ---------- Season stat categories ----------


def build_season_stat_categories(session: Session) -> list[GridCategory]:
    """\"+N stat in a single season\" — qualifier is ANY season meeting the threshold."""
    rows = session.query(
        PlayerSeason.player_id,
        PlayerSeason.ppg,
        PlayerSeason.rpg,
        PlayerSeason.apg,
        PlayerSeason.spg,
        PlayerSeason.bpg,
    ).all()
    if not rows:
        return []

    qualifiers: dict[str, set[int]] = defaultdict(set)
    for pid, ppg, rpg, apg, spg, bpg in rows:
        if (ppg or 0) >= 20:
            qualifiers["ppg20"].add(pid)
        if (rpg or 0) >= 10:
            qualifiers["rpg10"].add(pid)
        if (apg or 0) >= 8:
            qualifiers["apg8"].add(pid)
        if (spg or 0) >= 2:
            qualifiers["spg2"].add(pid)
        if (bpg or 0) >= 2:
            qualifiers["bpg2"].add(pid)

    buckets = [
        (
            "season_ppg20",
            "20+ PPG Season",
            "Averaged 20 or more points per game in at least one season.",
            "assets/category_icons/season/ppg.png",
            qualifiers["ppg20"],
        ),
        (
            "season_rpg10",
            "10+ RPG Season",
            "Averaged 10 or more rebounds per game in at least one season.",
            "assets/category_icons/season/rpg.png",
            qualifiers["rpg10"],
        ),
        (
            "season_apg8",
            "8+ APG Season",
            "Averaged 8 or more assists per game in at least one season.",
            "assets/category_icons/season/apg.png",
            qualifiers["apg8"],
        ),
        (
            "season_spg2",
            "2+ SPG Season",
            "Averaged 2 or more steals per game in at least one season.",
            "assets/category_icons/season/spg.png",
            qualifiers["spg2"],
        ),
        (
            "season_bpg2",
            "2+ BPG Season",
            "Averaged 2 or more blocks per game in at least one season.",
            "assets/category_icons/season/bpg.png",
            qualifiers["bpg2"],
        ),
    ]
    return [
        GridCategory(
            id=cid,
            family="season_stat",
            display_name=label,
            description=desc,
            icon_url=icon,
            icon_kind="trophy",
            valid_player_ids=sorted(ids),
        )
        for cid, label, desc, icon, ids in buckets
        if len(ids) >= MIN_CATEGORY_PLAYERS
    ]


# ---------- Team count ----------


def build_team_count_categories(session: Session) -> list[GridCategory]:
    league = session.query(League).filter(League.slug == "nba").first()
    if league is None:
        return []

    rows = (
        session.query(ClubPlayer.player_id)
        .join(Club, Club.id == ClubPlayer.club_id)
        .filter(Club.league_id == league.id)
        .all()
    )
    counts: dict[int, int] = defaultdict(int)
    for (pid,) in rows:
        counts[pid] += 1

    icon = "assets/category_icons/teams/multi_jerseys.png"
    buckets = [
        (
            "teams_3plus",
            "Played for 3+ Teams",
            "Appeared for three or more distinct NBA franchises.",
            3,
        ),
        (
            "teams_4plus",
            "Played for 4+ Teams",
            "Appeared for four or more distinct NBA franchises.",
            4,
        ),
        (
            "teams_5plus",
            "Played for 5+ Teams",
            "Appeared for five or more distinct NBA franchises.",
            5,
        ),
    ]
    out: list[GridCategory] = []
    for cid, label, desc, threshold in buckets:
        ids = _unique(pid for pid, c in counts.items() if c >= threshold)
        if len(ids) >= MIN_CATEGORY_PLAYERS:
            out.append(
                GridCategory(
                    id=cid,
                    family="team_count",
                    display_name=label,
                    description=desc,
                    icon_url=icon,
                    icon_kind="logo",
                    valid_player_ids=ids,
                )
            )
    return out


# ---------- Coaches ----------


def build_coach_categories(session: Session) -> list[GridCategory]:
    coaches = session.query(Coach).all()
    if not coaches:
        return []

    out: list[GridCategory] = []
    for coach in coaches:
        player_ids = _unique(
            pid
            for (pid,) in session.query(CoachPlayer.player_id)
            .filter(CoachPlayer.coach_id == coach.id)
            .all()
        )
        if len(player_ids) < MIN_CATEGORY_PLAYERS:
            continue
        out.append(
            GridCategory(
                id=f"coach_{coach.name_normalized.replace(' ', '_')}",
                family="coach",
                display_name=f"Coached by {coach.name}",
                description=f"Played at least one game under head coach {coach.name}.",
                icon_url=coach.headshot_url,
                icon_kind="portrait",
                valid_player_ids=player_ids,
            )
        )
    return out


# ---------- Birthplace ----------


def build_birthplace_categories(session: Session) -> list[GridCategory]:
    """European / Born-outside-USA from `players.birth_country` + `is_european`."""
    players = session.query(Player.id, Player.birth_country, Player.is_european).all()
    if not any(bc is not None for _, bc, _ in players):
        return []

    european: list[int] = [pid for pid, _bc, eu in players if eu]
    non_usa: list[int] = [pid for pid, bc, _eu in players if bc is not None and bc != "USA"]

    out: list[GridCategory] = []
    if len(european) >= MIN_CATEGORY_PLAYERS:
        out.append(
            GridCategory(
                id="birth_european",
                family="birthplace",
                display_name="European Player",
                description="Born in a European country.",
                icon_url="assets/category_icons/birth/european.png",
                icon_kind="trophy",
                valid_player_ids=_unique(european),
            )
        )
    if len(non_usa) >= MIN_CATEGORY_PLAYERS:
        out.append(
            GridCategory(
                id="birth_non_usa",
                family="birthplace",
                display_name="Born Outside the USA",
                description="Born in any country other than the United States.",
                icon_url="assets/category_icons/birth/non_usa.png",
                icon_kind="trophy",
                valid_player_ids=_unique(non_usa),
            )
        )
    return out


# ---------- Entry point ----------


def build_all_categories(session: Session) -> list[GridCategory]:
    """Always includes real-data families (team, team_count). Synthetic
    families are only included when `TRUST_METADATA_FAMILIES` is True — set
    that flag once the real scrape has replaced the mock metadata file.
    """
    categories: list[GridCategory] = build_team_categories(session) + build_team_count_categories(
        session
    )
    if TRUST_METADATA_FAMILIES:
        categories += (
            build_award_categories(session)
            + build_draft_categories(session)
            + build_decade_categories(session)
            + build_career_stat_categories(session)
            + build_season_stat_categories(session)
            + build_coach_categories(session)
            + build_birthplace_categories(session)
        )
    return categories
