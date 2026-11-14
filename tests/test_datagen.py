"""Synthetic data: planted patterns are really planted, and the control is isomorphic."""
from __future__ import annotations

from minerllm.datagen import PLANTED, UniversitySpec, generate, write_dataset
from minerllm.datasets import load_atoms, stats
from minerllm.oracle import Oracle


def test_generation_is_deterministic():
    assert generate(UniversitySpec(seed=3))[0] == generate(UniversitySpec(seed=3))[0]


def test_planted_patterns_beat_the_no_signal_version():
    strong = Oracle(generate(UniversitySpec(strength=0.8))[0])
    none = Oracle(generate(UniversitySpec(strength=0.0))[0])
    for name in ("P1_major_in_advisor_dept", "P2_enrolled_in_advisor_course"):
        assert strong.support(PLANTED[name]) > 2.5 * none.support(PLANTED[name]), name


def test_structural_pattern_holds_for_every_course():
    spec = UniversitySpec()
    o = Oracle(generate(spec)[0])
    assert o.support(PLANTED["P3_course_offered_by_teacher_dept"]) == spec.courses


def test_anonymised_control_is_isomorphic():
    named_atoms, named = generate(UniversitySpec(seed=1))
    anon_atoms, anon = generate(UniversitySpec(seed=1, anonymize=True))
    assert len(named_atoms) == len(anon_atoms)
    assert not any(a[0] in named["planted"] for a in anon_atoms)
    assert all(a[0].startswith("R") for a in anon_atoms)
    n, a = Oracle(named_atoms), Oracle(anon_atoms)
    for key in named["planted"]:
        assert n.support(named["planted"][key]) == a.support(anon["planted"][key])
    assert sorted(stats(named_atoms).relations.values()) == sorted(stats(anon_atoms).relations.values())


def test_write_dataset_roundtrip(tmp_path):
    path = write_dataset(UniversitySpec(seed=2), tmp_path)
    assert path.exists() and path.with_suffix("").with_suffix(".truth.json").exists()
    assert load_atoms(path) == [tuple(a) for a in generate(UniversitySpec(seed=2))[0]]
