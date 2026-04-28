"""
Smoke tests for the AMT Python package.

Uses the Potter Attribution example shipped with the original web tool.
"""
from pathlib import Path

import pytest

from amt import (
    check_consistency,
    do_reasoning,
    export_cypher,
    export_ttl,
    load_amt,
)

EXAMPLE = Path(__file__).parent.parent / "examples" / "PotterAttributionExample.ttl"


@pytest.fixture(scope="module")
def amt():
    assert EXAMPLE.exists(), f"missing example file: {EXAMPLE}"
    return load_amt(EXAMPLE)


def test_load_returns_expected_keys(amt):
    for k in ("concepts", "roles", "nodes", "edges", "axioms", "graph", "prefix"):
        assert k in amt


def test_potter_example_has_content(amt):
    # The Potter example is non-trivial – just sanity-check shape.
    assert len(amt["concepts"]) >= 1
    assert len(amt["roles"]) >= 1
    assert len(amt["nodes"]) >= 1
    assert len(amt["edges"]) >= 1


def test_reasoning_is_idempotent(amt):
    once = do_reasoning(amt["edges"], amt["axioms"])
    twice = do_reasoning(once, amt["axioms"])
    # do_reasoning() runs to a fixed point, so a second pass adds nothing new
    # beyond what the first one produced.
    assert len(twice) == len(once)


def test_reasoning_does_not_mutate_input(amt):
    before = len(amt["edges"])
    _ = do_reasoning(amt["edges"], amt["axioms"])
    assert len(amt["edges"]) == before


def test_consistency_returns_tuple(amt):
    ok, violations = check_consistency(amt["edges"], amt["axioms"])
    assert isinstance(ok, bool)
    assert isinstance(violations, list)
    if ok:
        assert violations == []


def test_export_ttl_round_trip(amt, tmp_path):
    ttl = export_ttl(
        amt["nodes"], amt["edges"], amt["concepts"], amt["roles"],
        amt["axioms"], rdf_graph=amt["graph"], prefix=amt["prefix"],
    )
    out = tmp_path / "round_trip.ttl"
    out.write_text(ttl, encoding="utf-8")

    reloaded = load_amt(out)
    assert len(reloaded["concepts"]) == len(amt["concepts"])
    assert len(reloaded["roles"])    == len(amt["roles"])
    assert len(reloaded["nodes"])    == len(amt["nodes"])
    assert len(reloaded["edges"])    == len(amt["edges"])
    assert len(reloaded["axioms"])   == len(amt["axioms"])  # axioms must survive

    # Axioms should reason to the same number of inferred edges after re-import
    inferred_orig     = [e for e in do_reasoning(amt["edges"], amt["axioms"])      if e.get("inferred")]
    inferred_reloaded = [e for e in do_reasoning(reloaded["edges"], reloaded["axioms"]) if e.get("inferred")]
    assert len(inferred_orig) == len(inferred_reloaded)


def test_export_cypher_starts_with_header(amt):
    cy = export_cypher(amt["nodes"], amt["edges"], amt["axioms"])
    assert cy.startswith("// AMT Cypher export")
    assert "MERGE" in cy
    assert cy.rstrip().endswith("RETURN *")


def test_export_with_reasoning_includes_inferred_flag(amt):
    cy = export_cypher(amt["nodes"], amt["edges"], amt["axioms"], with_reasoning=True)
    # If the example produces no inferences this assertion is too strong;
    # in that case we only require that the call succeeds.
    reasoned = do_reasoning(amt["edges"], amt["axioms"])
    if any(e.get("inferred") for e in reasoned):
        assert "inferred: true" in cy
