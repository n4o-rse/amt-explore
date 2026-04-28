"""
AMT Core Engine
===============

Python port of ``amt.js`` from the Academic Meta Tool
(http://academic-meta-tool.xyz/).

Three pure functions, no global state:

* :func:`load_amt`         – parse a TTL file/string into Concepts, Roles,
                             Nodes, Edges and Axioms
* :func:`do_reasoning`     – apply RoleChain and Inverse axioms iteratively
* :func:`check_consistency` – check Disjoint and SelfDisjoint axioms

The data structures returned by :func:`load_amt` are plain ``dict``/``list``
objects so they survive serialisation and can be passed around freely.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import TypedDict

from rdflib import Graph, Namespace, RDF, RDFS, URIRef

# AMT vocabulary namespace
AMT = Namespace("http://academic-meta-tool.xyz/vocab#")
AMT_PFX = str(AMT)


# ─────────────────────────────────────────────────────────────────────────────
# Type hints (lightweight – not enforced, just for readability)
# ─────────────────────────────────────────────────────────────────────────────
class Concept(TypedDict):
    iri: str
    label: str
    placeholder: str


class Role(TypedDict):
    iri: str
    label: str
    domain: str
    range: str


class Node(TypedDict):
    id: str
    label: str
    concept: str


class Edge(TypedDict, total=False):
    role: str
    from_: str  # NB: keyed as "from" in the actual dict – Python keyword clash
    to: str
    weight: float
    inferred: bool


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def local_name(iri: str) -> str:
    """Return the local name of an IRI (after the last ``#`` or ``/``)."""
    return str(iri).split("/")[-1].split("#")[-1]


# Kept as a private alias for the inferred-edge helper functions below
_local = local_name


# ─────────────────────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────────────────────
def load_amt(ttl_source: str | Path) -> dict:
    """
    Parse a Turtle source and extract all AMT components.

    Parameters
    ----------
    ttl_source
        Path to a ``.ttl`` file, or a raw Turtle string.

    Returns
    -------
    dict
        Keys: ``concepts``, ``roles``, ``nodes``, ``edges``, ``axioms``,
        ``graph`` (the underlying :class:`rdflib.Graph`),
        ``prefix`` (best-guess instance prefix, used by exporters).
    """
    g = Graph()
    src = str(ttl_source)
    if Path(src).exists():
        g.parse(src, format="turtle")
    else:
        g.parse(data=src, format="turtle")

    # ── Concepts ────────────────────────────────────────────────────────────
    concepts: dict[str, Concept] = {}
    for c in g.subjects(RDF.type, AMT.Concept):
        label = str(g.value(c, RDFS.label) or _local(c))
        placeholder = str(g.value(c, AMT.placeholder) or label)
        concepts[str(c)] = {"iri": str(c), "label": label, "placeholder": placeholder}

    # ── Roles ───────────────────────────────────────────────────────────────
    roles: dict[str, Role] = {}
    for r in sorted(
        g.subjects(RDF.type, AMT.Role),
        key=lambda x: str(g.value(x, RDFS.label) or x),
    ):
        label = str(g.value(r, RDFS.label) or _local(r))
        domain = str(g.value(r, RDFS.domain) or "")
        range_ = str(g.value(r, RDFS.range) or "")
        roles[str(r)] = {
            "iri": str(r),
            "label": label,
            "domain": domain,
            "range": range_,
        }

    # ── Nodes (instances) ───────────────────────────────────────────────────
    nodes: dict[str, Node] = {}
    for concept_iri in concepts:
        for inst in g.subjects(AMT.instanceOf, URIRef(concept_iri)):
            label = str(g.value(inst, RDFS.label) or _local(inst))
            nodes[str(inst)] = {
                "id": str(inst),
                "label": label,
                "concept": concept_iri,
            }

    # ── Edges (reified statements with weight) ──────────────────────────────
    edges: list[dict] = []
    for stmt in g.subjects(AMT.weight, None):
        frm = g.value(stmt, RDF.subject)
        role = g.value(stmt, RDF.predicate)
        to = g.value(stmt, RDF.object)
        w = g.value(stmt, AMT.weight)
        if frm and role and to and w is not None:
            edges.append(
                {
                    "role": str(role),
                    "from": str(frm),
                    "to": str(to),
                    "weight": min(float(w), 1.0),
                }
            )

    # ── Axioms ──────────────────────────────────────────────────────────────
    axiom_types: set = set()
    for cls in g.subjects(RDFS.subClassOf, AMT.Axiom):
        axiom_types.add(cls)
        for sub in g.subjects(RDFS.subClassOf, cls):
            axiom_types.add(sub)

    axioms: list[dict] = []
    for atype in axiom_types:
        for axiom in g.subjects(RDF.type, atype):
            entry: dict = {"type": _local(atype)}
            for _, p, o in g.triples((axiom, None, None)):
                if p != RDF.type:
                    entry[_local(p)] = str(o)
            axioms.append(entry)

    # ── Best-guess prefix (used by exporters for short ``ex:`` names) ───────
    prefix = ""
    if nodes:
        first_id = next(iter(nodes.values()))["id"]
        prefix = first_id.rsplit("/", 1)[0] + "/"

    return {
        "concepts": concepts,
        "roles": roles,
        "nodes": nodes,
        "edges": edges,
        "axioms": axioms,
        "graph": g,
        "prefix": prefix,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning
# ─────────────────────────────────────────────────────────────────────────────
def _conjunction(x: float, y: float, logic: str) -> float:
    """Fuzzy conjunction operators – mirrors ``amt.js``."""
    if logic == AMT_PFX + "LukasiewiczLogic":
        return max(x + y - 1, 0.0)
    if logic == AMT_PFX + "ProductLogic":
        return x * y
    if logic == AMT_PFX + "GoedelLogic":
        return min(x, y)
    return 0.0


def do_reasoning(edges: list, axioms: list) -> list:
    """
    Apply RoleChain and Inverse axioms iteratively until a fixed point is
    reached. Inferred edges are tagged with ``{'inferred': True}``.

    The input ``edges`` list is **not** modified; a new list is returned.
    """
    result = copy.deepcopy(edges)

    def _find(role, frm, to):
        return next(
            (
                e
                for e in result
                if e["role"] == role and e["from"] == frm and e["to"] == to
            ),
            None,
        )

    changed = True
    while changed:
        changed = False
        for axiom in axioms:

            if axiom["type"] == "RoleChainAxiom":
                ant1 = axiom.get("antecedent1")
                ant2 = axiom.get("antecedent2")
                cons = axiom.get("consequent")
                logic = axiom.get("logic", "")
                for e1 in list(result):
                    for e2 in list(result):
                        if (
                            e1["to"] == e2["from"]
                            and e1["role"] == ant1
                            and e2["role"] == ant2
                        ):
                            w = _conjunction(e1["weight"], e2["weight"], logic)
                            if w <= 0:
                                continue
                            w = min(round(w, 6), 1.0)
                            existing = _find(cons, e1["from"], e2["to"])
                            if existing is None:
                                result.append(
                                    {
                                        "role": cons,
                                        "from": e1["from"],
                                        "to": e2["to"],
                                        "weight": w,
                                        "inferred": True,
                                    }
                                )
                                changed = True
                            elif existing["weight"] < w:
                                existing["weight"] = w
                                changed = True

            elif axiom["type"] == "InverseAxiom":
                ant = axiom.get("antecedent")
                inv = axiom.get("inverse")
                for e in list(result):
                    if e["role"] == ant:
                        existing = _find(inv, e["to"], e["from"])
                        if existing is None:
                            result.append(
                                {
                                    "role": inv,
                                    "from": e["to"],
                                    "to": e["from"],
                                    "weight": e["weight"],
                                    "inferred": True,
                                }
                            )
                            changed = True
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Consistency
# ─────────────────────────────────────────────────────────────────────────────
def check_consistency(edges: list, axioms: list) -> tuple[bool, list[str]]:
    """
    Check ``DisjointAxiom`` and ``SelfDisjointAxiom`` integrity constraints
    against the reasoned edge set.

    Returns
    -------
    (is_consistent, violations)
        ``violations`` is a list of human-readable strings; empty when
        ``is_consistent`` is ``True``.
    """
    reasoned = do_reasoning(edges, axioms)
    violations: list[str] = []

    def _find(role, frm, to):
        return next(
            (
                e
                for e in reasoned
                if e["role"] == role and e["from"] == frm and e["to"] == to
            ),
            None,
        )

    for axiom in axioms:
        if axiom["type"] == "DisjointAxiom":
            r1, r2 = axiom.get("role1"), axiom.get("role2")
            for e in reasoned:
                if e["role"] == r1 and _find(r2, e["from"], e["to"]):
                    violations.append(
                        f"DisjointAxiom violated: {_local(e['from'])} "
                        f"has both {_local(r1)} and {_local(r2)} "
                        f"to {_local(e['to'])}"
                    )
        if axiom["type"] == "SelfDisjointAxiom":
            role = axiom.get("role")
            for e in reasoned:
                if e["role"] == role and e["from"] == e["to"]:
                    violations.append(
                        f"SelfDisjointAxiom violated: "
                        f"{_local(e['from'])} has self-loop via {_local(role)}"
                    )

    return (len(violations) == 0, violations)
