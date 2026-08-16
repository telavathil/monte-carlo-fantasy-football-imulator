import json
import pathlib
from datetime import datetime
from app.import_pipeline.stats_importer import import_stats
from app.import_pipeline.adp_importer import import_adp
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, ImportBatch, ImportUnresolved,
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
