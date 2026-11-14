"""Synthetic knowledge graphs with planted, known-surprising patterns.

Why synthetic data? Real data has no answer key. Here we *plant* dependencies,
so we know which conjunctions should come out surprising, and we can switch them
off (``strength=0``) to check that they then stop being surprising.

Domain: a university.

    ADVISED_BY(student, prof)   MAJORS_IN(student, dept)   ENROLLED_IN(student, course)
    MEMBER_OF(prof, dept)       TEACHES(prof, course)      OFFERED_BY(course, dept)
    noise: FRIENDS_WITH(student, student), HELD_IN(course, room), USES(student, laptop)

Planted dependencies (each with probability ``strength``, otherwise random):

    P1  a student majors in their advisor's department
        (, (ADVISED_BY $s $p) (MEMBER_OF $p $d) (MAJORS_IN $s $d))
    P2  a student takes a course taught by their advisor
        (, (ADVISED_BY $s $p) (TEACHES $p $c) (ENROLLED_IN $s $c))
    P3  a course is offered by its teacher's department (always true: structural)
        (, (TEACHES $p $c) (MEMBER_OF $p $d) (OFFERED_BY $c $d))

**Anonymised control.** ``anonymize=True`` renames relations to R1..R9 and entities
to e1..eN, keeping the graph isomorphic. Any advantage the LLM ranker has on the
named version but loses on the anonymised one comes from world knowledge in the
names. That's the main ablation in Step 6.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .sexpr import Var, dumps, parse

PLANTED = {
    "P1_major_in_advisor_dept": "(, (ADVISED_BY $s $p) (MEMBER_OF $p $d) (MAJORS_IN $s $d))",
    "P2_enrolled_in_advisor_course": "(, (ADVISED_BY $s $p) (TEACHES $p $c) (ENROLLED_IN $s $c))",
    "P3_course_offered_by_teacher_dept": "(, (TEACHES $p $c) (MEMBER_OF $p $d) (OFFERED_BY $c $d))",
}
RELATIONS = ["ADVISED_BY", "MAJORS_IN", "ENROLLED_IN", "MEMBER_OF", "TEACHES",
             "OFFERED_BY", "FRIENDS_WITH", "HELD_IN", "USES"]


@dataclass
class UniversitySpec:
    students: int = 60
    profs: int = 12
    courses: int = 24
    depts: int = 4
    rooms: int = 8
    laptops: int = 6
    courses_per_student: int = 3
    friends_per_student: int = 1
    strength: float = 0.8
    seed: int = 0
    anonymize: bool = False


def generate(spec: UniversitySpec) -> tuple[list[tuple], dict]:
    """Return (atoms, ground_truth)."""
    rng = random.Random(spec.seed)
    S = [f"student_{i}" for i in range(spec.students)]
    P = [f"prof_{i}" for i in range(spec.profs)]
    C = [f"course_{i}" for i in range(spec.courses)]
    D = [f"dept_{i}" for i in range(spec.depts)]
    R = [f"room_{i}" for i in range(spec.rooms)]
    L = [f"laptop_{i}" for i in range(spec.laptops)]

    atoms: list[tuple] = []
    dept_of = {p: D[i % len(D)] for i, p in enumerate(P)}
    teacher = {c: P[i % len(P)] for i, c in enumerate(C)}
    courses_of = {p: [c for c in C if teacher[c] == p] for p in P}

    for p in P:
        atoms.append(("MEMBER_OF", p, dept_of[p]))
    for c in C:
        atoms.append(("TEACHES", teacher[c], c))
        atoms.append(("OFFERED_BY", c, dept_of[teacher[c]]))          # P3 (structural)
        atoms.append(("HELD_IN", c, rng.choice(R)))                    # noise

    for s in S:
        adv = rng.choice(P)
        atoms.append(("ADVISED_BY", s, adv))
        major = dept_of[adv] if rng.random() < spec.strength else rng.choice(D)   # P1
        atoms.append(("MAJORS_IN", s, major))
        chosen: set[str] = set()
        if rng.random() < spec.strength and courses_of[adv]:              # P2
            chosen.add(rng.choice(courses_of[adv]))
        while len(chosen) < spec.courses_per_student:
            chosen.add(rng.choice(C))
        atoms.extend(("ENROLLED_IN", s, c) for c in sorted(chosen))
        for f in rng.sample([x for x in S if x != s], spec.friends_per_student):
            atoms.append(("FRIENDS_WITH", s, f))                      # noise
        atoms.append(("USES", s, rng.choice(L)))                       # noise

    truth = {"spec": asdict(spec), "planted": dict(PLANTED), "relation_map": {}}
    if spec.anonymize:
        atoms, truth = _anonymize(atoms, truth, rng)
    return atoms, truth


def _anonymize(atoms: list[tuple], truth: dict, rng: random.Random) -> tuple[list[tuple], dict]:
    rels = RELATIONS[:]
    rng.shuffle(rels)
    rel_map = {r: f"R{i + 1}" for i, r in enumerate(rels)}
    ents = sorted({x for a in atoms for x in a[1:]})
    rng.shuffle(ents)
    ent_map = {e: f"e{i + 1}" for i, e in enumerate(ents)}
    new_atoms = [(rel_map[a[0]], *(ent_map[x] for x in a[1:])) for a in atoms]

    def rename(pattern: str) -> str:
        def walk(x):
            if isinstance(x, tuple):
                return tuple(walk(y) for y in x)
            return rel_map.get(x, x) if not isinstance(x, Var) else x
        return dumps(walk(parse(pattern)))

    truth = dict(truth)
    truth["planted"] = {k: rename(v) for k, v in truth["planted"].items()}
    truth["relation_map"] = rel_map
    return new_atoms, truth


def write_dataset(spec: UniversitySpec, out_dir: str | Path, name: str | None = None) -> Path:
    """Write ``<name>.metta`` and ``<name>.truth.json``; return the .metta path."""
    atoms, truth = generate(spec)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = name or (f"university_s{spec.seed}_st{int(spec.strength * 100)}"
                    + ("_anon" if spec.anonymize else ""))
    header = [f";; Synthetic university graph ({len(atoms)} atoms) — minerllm.datagen",
              f";; spec: {json.dumps(asdict(spec))}"]
    path = out_dir / f"{name}.metta"
    path.write_text("\n".join(header + [dumps(a) for a in atoms]) + "\n")
    (out_dir / f"{name}.truth.json").write_text(json.dumps(truth, indent=2))
    return path
