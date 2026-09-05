import json
import pathlib
from datetime import datetime
from app.import_pipeline.stats_importer import import_stats
from app.import_pipeline.adp_importer import import_adp
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, ImportBatch, ImportUnresolved,
    PlayerDistributionParams,
)


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def _seed_canonical(session):
    """Seed a minimal canonical player table for Tier-3 matches against the FP QB fixture."""
    now = datetime.utcnow().isoformat()
    players = [
        Player(mfl_id=1, gsis_id="00-0033873", name="Patrick Mahomes",
               merge_name="patrick mahomes", team="KCC", position="QB",
               seeded_at=now),
        Player(mfl_id=2, gsis_id="00-0034796", name="Josh Allen",
               merge_name="josh allen", team="BUF", position="QB",
               seeded_at=now),
        Player(mfl_id=3, gsis_id="00-0035228", name="Lamar Jackson",
               merge_name="lamar jackson", team="BAL", position="QB",
               seeded_at=now),
    ]
    session.add_all(players)
    session.commit()


def test_import_stats_fp_qb_happy_path(session):
    _seed_canonical(session)
    content = (FIXTURES / "fantasypros_qb.html").read_bytes()
    batch_id, summary = import_stats(
        session, content=content, filename="fantasypros_qb.html",
        source="fantasypros", position="QB",
    )
    batch = session.get(ImportBatch, batch_id)
    assert batch.kind == "stats"
    assert batch.source == "fantasypros"
    assert batch.position == "QB"
    # At least the 3 seeded QBs should match via Tier 3
    projections = session.query(PlayerProjection).filter_by(import_batch_id=batch_id).all()
    assert len(projections) >= 3
    # Mahomes' stats are JSON-parseable with expected keys
    mahomes_proj = session.query(PlayerProjection).filter_by(player_id=1).first()
    stats = json.loads(mahomes_proj.stats)
    assert "passing_yards" in stats


def test_import_stats_unresolved_rows_tracked(session):
    _seed_canonical(session)  # only 3 QBs seeded; rest of FP table will be unresolved
    content = (FIXTURES / "fantasypros_qb.html").read_bytes()
    _, summary = import_stats(session, content=content,
                              filename="fantasypros_qb.html",
                              source="fantasypros", position="QB")
    unresolved = session.query(ImportUnresolved).all()
    assert len(unresolved) > 0
    # Parsed name + team are captured
    for u in unresolved[:3]:
        assert u.parsed_name
        assert u.parsed_team


def test_import_adp_stub(session):
    _seed_canonical(session)
    csv = b"Player,Team,adp_snake,adp_auction\nPatrick Mahomes,KC,18.5,32\n"
    batch_id, _ = import_adp(session, content=csv, filename="fp_adp.csv",
                             source="fantasypros")
    adp = session.query(PlayerAdp).filter_by(import_batch_id=batch_id).first()
    assert adp is not None
    assert adp.adp_snake == 18.5


def test_reimport_stats_invalidates_cached_distribution_params(session):
    """Regression for: cached PlayerDistributionParams rows were never
    invalidated when a player's projection changed via a new stats import,
    so /distribution kept serving a distribution fit to a stale projection."""
    _seed_canonical(session)
    content = (FIXTURES / "fantasypros_qb.html").read_bytes()
    import_stats(session, content=content, filename="fantasypros_qb.html",
                 source="fantasypros", position="QB")

    # Simulate a prior fit having been cached for Mahomes (mfl_id=1). Fitting
    # for real requires historical game logs not available to this test's
    # fixtures, so insert the cached row directly.
    session.add(PlayerDistributionParams(
        player_id=1,
        params=json.dumps({"passing_yards": [1.0, 2.0]}),
        fitted_at=datetime.utcnow().isoformat(),
        historical_seasons="2023,2024,2025",
        games_used=16,
    ))
    session.commit()
    assert session.get(PlayerDistributionParams, 1) is not None

    # Re-import an updated projection for the same player.
    import_stats(session, content=content, filename="fantasypros_qb.html",
                 source="fantasypros", position="QB")

    assert session.get(PlayerDistributionParams, 1) is None


def test_import_adp_malformed_row_does_not_lose_whole_batch(session):
    """Regression for: one bad row previously raised uncaught, losing the
    entire batch's work (including successfully-processed rows before it)
    since the exception propagated before session.commit()."""
    _seed_canonical(session)
    csv = (
        b"Player,Team,adp_snake,adp_auction\n"
        b"Patrick Mahomes,KC,18.5,32\n"
        b"Josh Allen,BUF,not-a-number,10\n"  # malformed: non-numeric ADP value
    )
    batch_id, summary = import_adp(session, content=csv, filename="fp_adp.csv",
                                   source="fantasypros")

    batch = session.get(ImportBatch, batch_id)
    assert batch is not None  # batch persisted; did not 500 before commit
    assert batch.matched_rows == 1
    assert batch.unresolved_rows == 1
    assert batch.status == "partial"

    adp_rows = session.query(PlayerAdp).filter_by(import_batch_id=batch_id).all()
    assert len(adp_rows) == 1
    assert adp_rows[0].player_id == 1
    assert adp_rows[0].adp_snake == 18.5

    unresolved = session.query(ImportUnresolved).filter_by(import_batch_id=batch_id).all()
    assert len(unresolved) == 1
    assert "error" in (unresolved[0].resolution or "")


def test_import_adp_no_position_column_resolves_non_qb(session):
    # Real-world overall ADP exports are not split by position, so there is
    # usually no `position` column at all. A non-QB player (e.g. a WR) must
    # still resolve correctly via name+team alone.
    _seed_canonical(session)
    session.add(Player(mfl_id=4, gsis_id="00-0036264", name="CeeDee Lamb",
                       merge_name="ceedee lamb", team="DAL", position="WR",
                       seeded_at=datetime.utcnow().isoformat()))
    session.commit()
    csv = b"Player,Team,adp_snake,adp_auction\nCeeDee Lamb,DAL,9.5,55\n"
    batch_id, _ = import_adp(session, content=csv, filename="overall_adp.csv",
                             source="fantasypros")
    adp = session.query(PlayerAdp).filter_by(import_batch_id=batch_id, player_id=4).first()
    assert adp is not None
    assert adp.adp_snake == 9.5
