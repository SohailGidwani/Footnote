from app.db import short_name
from app.matcher import Matcher, tokens


def test_company_pack_is_valid(pack):
    ids = {p["id"] for p in pack["people"]}
    assert len(pack["people"]) == 12 and len(pack["projects"]) == 8 and len(pack["terms"]) == 40
    assert all(p["email"].endswith("@halcyon.example") for p in pack["people"])
    assert all(j["lead_id"] in ids for j in pack["projects"])
    term_ids = [t["id"] for t in pack["terms"]]
    assert len(term_ids) == len(set(term_ids))
    people = {p["id"]: p for p in pack["people"]}
    for t in pack["terms"]:
        assert t["owner_id"] in ids, t["id"]
        assert len(t["term"]) <= 24, t["term"]            # card.term (uppercased, same length)
        assert len(t["meaning"]) <= 44, t["meaning"]      # card.line1
        owner = people[t["owner_id"]]
        assert len(short_name(owner["name"])) + len(owner["team"]) <= 40
        assert t["meaning"].isascii() and t["term"].isascii()
    names = {t["term"].lower() for t in pack["terms"]}
    for required in ("bluebird", "fcs", "golden path", "q4 bake-off", "sev2", "kestrel", "dri", "2pm platform sync"):
        assert required in names
    bluebird = next(t for t in pack["terms"] if t["term"] == "Bluebird")
    assert bluebird["meaning"] == "v3 navigation stack rewrite"
    assert people[bluebird["owner_id"]]["name"].startswith("Priya R") and people[bluebird["owner_id"]]["team"] == "Autonomy"
    assert "hal-9" not in names  # reserved for the StepFun slow-path check


def test_tokens_normalize_spoken_variants():
    assert tokens("F.C.S.") == ["fcs"]
    assert tokens("SEV two, please") == ["sev", "2", "please"]
    assert tokens("at 2 p.m.") == ["at", "2", "pm"]


def matcher_for(pack):
    return Matcher([{**t, "aliases": t["aliases"]} for t in pack["terms"]])


def test_matcher_finds_terms_in_order(pack):
    m = matcher_for(pack)
    found = m.find("Bluebird is slipping because FCS is still on the old golden path, so we might punt to the Q4 bake-off")
    assert found == ["t_bluebird", "t_fcs", "t_golden_path", "t_q4_bakeoff"]


def test_matcher_handles_stt_variants(pack):
    m = matcher_for(pack)
    assert m.find("the blue bird rewrite") == ["t_bluebird"]
    assert m.find("this is a sev two") == ["t_sev2"]
    assert m.find("we need SOC 2 first") == ["t_soc2"]
    assert m.find("see you at the 2 p.m. platform sync") == ["t_platform_sync"]
    assert m.find("who is the D.R.I. here") == ["t_dri"]
    assert m.find("the bake off was fun") == []


def test_short_acronyms_never_fuzzy_match_ordinary_words(pack):
    m = matcher_for(pack)
    assert m.find("the driver said that was a dry run, not an array or a bomb") == []
    assert m.find("we had a good lunch and talked about the weather") == []
