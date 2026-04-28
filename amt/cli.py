"""
Command-line interface for the Academic Meta Tool.

Usage examples
--------------
::

    amt input.ttl --info
    amt input.ttl --reason --export-ttl out.ttl
    amt input.ttl --reason --export-cypher out.cypher --export-html graph.html
    amt input.ttl --check

The CLI is intentionally thin – every flag maps to one library function.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    __version__,
    check_consistency,
    do_reasoning,
    export_cypher,
    export_ttl,
    load_amt,
    local_name,
    render_to_html,
)


def _print_summary(amt: dict) -> None:
    print(
        f"✓ {len(amt['concepts'])} Concepts | "
        f"{len(amt['roles'])} Roles | "
        f"{len(amt['nodes'])} Nodes | "
        f"{len(amt['edges'])} Edges | "
        f"{len(amt['axioms'])} Axioms"
    )


def _print_info(amt: dict) -> None:
    print("\n== Concepts ==")
    for c in amt["concepts"].values():
        print(f"  · {local_name(c['iri']):20s}  {c['label']}")
    print("\n== Roles ==")
    for r in amt["roles"].values():
        print(
            f"  · {local_name(r['iri']):20s}  "
            f"{local_name(r['domain'])} → {local_name(r['range'])}"
        )
    print("\n== Axioms ==")
    for a in amt["axioms"]:
        details = {k: local_name(v) for k, v in a.items() if k != "type"}
        print(f"  · {a['type']:20s}  {details}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="amt",
        description="Academic Meta Tool – Python edition",
    )
    p.add_argument("input", type=Path, help="AMT-compatible Turtle (.ttl) file")
    p.add_argument(
        "--reason",
        action="store_true",
        help="Apply RoleChain and Inverse axioms before export",
    )
    p.add_argument("--check", action="store_true", help="Run consistency check")
    p.add_argument("--info", action="store_true", help="Print ontology summary")

    p.add_argument("--export-ttl", type=Path, metavar="PATH",
                   help="Write Turtle output to PATH")
    p.add_argument("--export-cypher", type=Path, metavar="PATH",
                   help="Write Neo4J Cypher output to PATH")
    p.add_argument("--export-html", type=Path, metavar="PATH",
                   help="Write standalone interactive HTML graph to PATH")
    p.add_argument("--height", default="600px",
                   help="Canvas height for the HTML graph (default: 600px)")

    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.input.exists():
        print(f"✗ Input file not found: {args.input}", file=sys.stderr)
        return 2

    print(f"📂 Loading {args.input.name} …")
    amt = load_amt(args.input)
    _print_summary(amt)

    if args.info:
        _print_info(amt)

    if args.check:
        ok, violations = check_consistency(amt["edges"], amt["axioms"])
        if ok:
            print("\n✓ Consistency check passed.")
        else:
            print(f"\n✗ {len(violations)} consistency violation(s):")
            for v in violations:
                print(f"  · {v}")

    if args.reason:
        reasoned = do_reasoning(amt["edges"], amt["axioms"])
        inferred = [e for e in reasoned if e.get("inferred")]
        print(f"  → reasoning produced {len(inferred)} inferred edges")

    if args.export_ttl:
        ttl = export_ttl(
            amt["nodes"], amt["edges"], amt["concepts"], amt["roles"],
            amt["axioms"], rdf_graph=amt["graph"], prefix=amt["prefix"],
            with_reasoning=args.reason,
        )
        args.export_ttl.write_text(ttl, encoding="utf-8")
        print(f"✓ wrote {args.export_ttl}")

    if args.export_cypher:
        cy = export_cypher(
            amt["nodes"], amt["edges"], amt["axioms"],
            with_reasoning=args.reason,
        )
        args.export_cypher.write_text(cy, encoding="utf-8")
        print(f"✓ wrote {args.export_cypher}")

    if args.export_html:
        render_to_html(
            amt["nodes"], amt["edges"], amt["concepts"],
            output_path=args.export_html,
            reasoning=args.reason,
            axioms=amt["axioms"],
            height=args.height,
        )
        print(f"✓ wrote {args.export_html}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
