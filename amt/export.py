"""
AMT Exporters
=============

Python port of ``amt-export.js``.

* :func:`export_ttl`    – Turtle, round-trip-compatible with :func:`amt.core.load_amt`
* :func:`export_cypher` – Neo4J Cypher

Both accept ``with_reasoning=True`` to include inferred edges; inferred
triples carry an additional ``amt:inferred "true"^^xsd:boolean`` flag.
"""
from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph

from .core import do_reasoning, local_name


def export_ttl(
    nodes: dict,
    edges: list,
    concepts: dict,
    roles: dict,
    axioms: list,
    rdf_graph: Graph,           # kept in signature for API parity / future use
    prefix: str,
    *,
    with_reasoning: bool = False,
) -> str:
    """
    Serialise the current AMT state to Turtle.

    The output is **deterministic** and styled to match the JS exporter so
    diffs against the original web tool stay readable.
    """
    AMT_NS = "http://academic-meta-tool.xyz/vocab#"
    RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
    XSD_NS = "http://www.w3.org/2001/XMLSchema#"

    display_edges = do_reasoning(edges, axioms) if with_reasoning else edges
    base_count = len(edges)

    def pfx(iri: str) -> str:
        if not iri:
            return iri
        if prefix and iri.startswith(prefix):
            return "ex:" + iri[len(prefix):]
        if iri.startswith(AMT_NS):
            return "amt:" + iri[len(AMT_NS):]
        if iri.startswith(RDF_NS):
            return "rdf:" + iri[len(RDF_NS):]
        if iri.startswith(RDFS_NS):
            return "rdfs:" + iri[len(RDFS_NS):]
        if iri.startswith(XSD_NS):
            return "xsd:" + iri[len(XSD_NS):]
        return f"<{iri}>"

    lines: list[str] = [
        f"@prefix amt:  <{AMT_NS}> .",
        f"@prefix rdf:  <{RDF_NS}> .",
        f"@prefix rdfs: <{RDFS_NS}> .",
        f"@prefix xsd:  <{XSD_NS}> .",
        f"@prefix ex:   <{prefix}> .",
        "",
    ]

    # Concepts
    lines.append("# Concepts")
    for c in concepts.values():
        lines += [
            pfx(c["iri"]),
            "    rdf:type        amt:Concept ;",
            f'    rdfs:label      "{c["label"]}" ;',
            f'    amt:placeholder "{c["placeholder"]}" .',
            "",
        ]

    # Roles
    lines.append("# Roles")
    for r in roles.values():
        lines += [
            pfx(r["iri"]),
            "    rdf:type      amt:Role ;",
            f'    rdfs:label    "{r["label"]}" ;',
            f'    rdfs:domain   {pfx(r["domain"])} ;',
            f'    rdfs:range    {pfx(r["range"])} .',
            "",
        ]

    # Instances
    lines.append("# Instances")
    for n in nodes.values():
        lines += [
            pfx(n["id"]),
            f'    amt:instanceOf  {pfx(n["concept"])} ;',
            f'    rdfs:label      "{n["label"]}" .',
            "",
        ]

    # Axioms
    if axioms:
        # The reader needs the AMT vocabulary scaffolding so it knows that
        # e.g. `RoleChainAxiom rdfs:subClassOf amt:Axiom`. We declare the
        # subset that's actually in use.
        lines.append("# AMT vocabulary (needed for axiom recognition)")
        used_types = sorted({ax.get("type", "Axiom") for ax in axioms})
        lines.append("amt:Axiom rdfs:subClassOf rdfs:Class .")
        lines.append("amt:InferenceAxiom rdfs:subClassOf amt:Axiom .")
        lines.append("amt:IntegrityAxiom rdfs:subClassOf amt:Axiom .")
        # subClassOf for the concrete axiom kinds we know about
        _AXIOM_PARENT = {
            "RoleChainAxiom":    "InferenceAxiom",
            "InverseAxiom":      "InferenceAxiom",
            "DisjointAxiom":     "IntegrityAxiom",
            "SelfDisjointAxiom": "IntegrityAxiom",
        }
        for t in used_types:
            parent = _AXIOM_PARENT.get(t, "Axiom")
            lines.append(f"amt:{t} rdfs:subClassOf amt:{parent} .")
        lines.append("amt:Logic rdfs:subClassOf rdfs:Class .")
        lines.append("amt:LukasiewiczLogic rdf:type amt:Logic .")
        lines.append("amt:ProductLogic rdf:type amt:Logic .")
        lines.append("amt:GoedelLogic rdf:type amt:Logic .")
        lines.append("")

        lines.append("# Axioms")
        for idx, ax in enumerate(axioms, start=1):
            atype = ax.get("type", "Axiom")
            iri = f"ex:AX{idx:04d}"  # stable, deterministic IRI
            lines.append(f"{iri} rdf:type amt:{atype} .")
            for k, v in ax.items():
                if k == "type":
                    continue
                rendered = pfx(v) if isinstance(v, str) and v.startswith("http") else f'"{v}"'
                lines.append(f"{iri} amt:{k} {rendered} .")
            lines.append("")

    # Original assertions (reified statements)
    lines.append("# Original Assertions")
    for j, e in enumerate(display_edges[:base_count]):
        w = min(float(e["weight"]), 1.0)
        bn = f"_:a{j+1}"
        lines += [
            bn,
            f'    rdf:subject   {pfx(e["from"])} ;',
            f'    rdf:predicate {pfx(e["role"])} ;',
            f'    rdf:object    {pfx(e["to"])} ;',
            f'    amt:weight    "{w:.6f}"^^xsd:double .',
            "",
        ]

    if with_reasoning and len(display_edges) > base_count:
        lines.append("# Inferred Assertions")
        for k, e in enumerate(display_edges[base_count:]):
            w = min(float(e["weight"]), 1.0)
            bn = f"_:i{k+1}"
            lines += [
                bn,
                f'    rdf:subject    {pfx(e["from"])} ;',
                f'    rdf:predicate  {pfx(e["role"])} ;',
                f'    rdf:object     {pfx(e["to"])} ;',
                f'    amt:weight     "{w:.6f}"^^xsd:double ;',
                '    amt:inferred   "true"^^xsd:boolean .',
                "",
            ]

    return "\n".join(lines)


def export_cypher(
    nodes: dict,
    edges: list,
    axioms: list,
    *,
    with_reasoning: bool = False,
) -> str:
    """Serialise to Neo4J Cypher. Mirrors ``exportCypher()`` from ``amt-export.js``."""

    def cypher_safe(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", s)

    display_edges = do_reasoning(edges, axioms) if with_reasoning else edges
    base_count = len(edges)

    var_map = {n["id"]: cypher_safe(local_name(n["id"])) for n in nodes.values()}

    lines = [
        "// AMT Cypher export",
        f"// Nodes: {len(nodes)}  Edges: {len(display_edges)}",
        f"// (inferred: {len(display_edges) - base_count})",
        "",
    ]

    node_lines, var_list = [], []
    for n in nodes.values():
        var = var_map[n["id"]]
        label = cypher_safe(local_name(n["concept"]))
        lbl = n["label"].replace('"', '\\"')
        node_lines.append(
            f'MERGE ({var}:{label} {{id: "{local_name(n["id"])}"}})\n'
            f'  ON CREATE SET {var}.label = "{lbl}", '
            f'{var}.concept = "{local_name(n["concept"])}"'
        )
        var_list.append(var)

    lines.append("// Step 1: nodes")
    lines.append("\n".join(node_lines))
    lines.append("WITH " + ", ".join(var_list))
    lines.append("")
    lines.append("// Step 2: relationships")

    for e in display_edges:
        w = round(min(float(e["weight"]), 1.0), 6)
        rel = cypher_safe(local_name(e["role"])).upper()
        fv = var_map.get(e["from"], cypher_safe(local_name(e["from"])))
        tv = var_map.get(e["to"], cypher_safe(local_name(e["to"])))
        inferred = "true" if e.get("inferred") else "false"
        lines.append(
            f"MERGE ({fv})-[:{rel} {{weight: {w}, "
            f'role: "{local_name(e["role"])}", inferred: {inferred}}}]->({tv})'
        )

    lines += ["", "RETURN *"]
    return "\n".join(lines)


# Convenience wrappers ---------------------------------------------------------
def write_ttl(path: str | Path, *args, **kwargs) -> Path:
    """Convenience wrapper: :func:`export_ttl` + write to disk."""
    out = Path(path)
    out.write_text(export_ttl(*args, **kwargs), encoding="utf-8")
    return out


def write_cypher(path: str | Path, *args, **kwargs) -> Path:
    """Convenience wrapper: :func:`export_cypher` + write to disk."""
    out = Path(path)
    out.write_text(export_cypher(*args, **kwargs), encoding="utf-8")
    return out
