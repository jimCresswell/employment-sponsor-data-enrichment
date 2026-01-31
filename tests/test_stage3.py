from uk_sponsor_pipeline.stages.stage3_scoring import _parse_sic_list, _score_from_sic

def test_parse_sic_list():
    assert _parse_sic_list("62020;63110") == ["62020", "63110"]

def test_score_from_sic():
    assert _score_from_sic(["62020"]) >= 0.9
    assert _score_from_sic(["87100"]) < 0.5
