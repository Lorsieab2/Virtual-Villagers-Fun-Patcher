from src.mask_distribution_snapshot import (
    SPECIAL_ROLES,
    VillagerSnapshot,
    eligible_for_additive_distribution,
)


def make_snapshot(**changes):
    values = dict(
        record_key=7,
        name="Napu",
        parentage=(1, 2),
        skill_progress=(10, 20, 30, 40, 50),
        preferred_skill=3,
        likes=("fish", "rain"),
        dislikes=("fire",),
        head=4,
        body=8,
        nursing=False,
        elderly=False,
        health=100,
    )
    values.update(changes)
    return VillagerSnapshot(**values)


def test_fingerprint_ignores_record_key_but_tracks_identity_fields():
    assert make_snapshot(record_key=1).fingerprint() == make_snapshot(record_key=2).fingerprint()
    assert make_snapshot(name="Hoto").fingerprint() != make_snapshot().fingerprint()
    assert make_snapshot(parentage=None).fingerprint() != make_snapshot().fingerprint()


def test_special_roles_are_explicitly_excluded():
    assert SPECIAL_ROLES == {"golden_child", "tribal_chief", "retired_chief"}
    assert not eligible_for_additive_distribution(make_snapshot(special_role="golden_child"))
    assert eligible_for_additive_distribution(make_snapshot(special_role=None))

