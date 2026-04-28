"""
AMT Visualisation
=================

Python port of ``amt-render.js`` using ``pyvis`` (which wraps vis.js).

Two entry points:

* :func:`build_network` – returns a configured :class:`pyvis.network.Network`
* :func:`render_to_html` – writes a self-contained HTML file
"""
from __future__ import annotations

from pathlib import Path

from pyvis.network import Network

from .core import do_reasoning, local_name

# Same colour order as ``AMT_PALETTE`` in ``amt-render.js``
_PALETTE = [
    {"bg": "coral", "border": "#c05a00", "font": "#000"},
    {"bg": "#5b9bd5", "border": "#2e75b6", "font": "#fff"},
    {"bg": "#70ad47", "border": "#538135", "font": "#fff"},
    {"bg": "#ffc000", "border": "#c07a00", "font": "#000"},
    {"bg": "#7030a0", "border": "#4b1a6e", "font": "#fff"},
    {"bg": "#ed7d31", "border": "#843c00", "font": "#fff"},
]


def build_network(
    nodes: dict,
    edges: list,
    concepts: dict,
    *,
    reasoning: bool = False,
    axioms: list | None = None,
    height: str = "600px",
    notebook: bool = False,
) -> Network:
    """
    Build a configured :class:`pyvis.network.Network` for an AMT graph.

    Parameters
    ----------
    nodes, edges, concepts
        Output of :func:`amt.core.load_amt`.
    reasoning
        If ``True``, run :func:`amt.core.do_reasoning` first; inferred edges
        are drawn as red dashed arrows.
    axioms
        Required when ``reasoning=True``.
    height
        CSS height for the canvas, e.g. ``"600px"``.
    notebook
        Pass ``True`` only when calling from inside a Jupyter notebook *and*
        you want pyvis to use its inline-iframe mode.
    """
    display_edges = (
        do_reasoning(edges, axioms or []) if reasoning else edges
    )

    net = Network(
        height=height,
        width="100%",
        directed=True,
        notebook=notebook,
        bgcolor="#ffffff",
        font_color="#333333",
        cdn_resources="remote",
    )
    net.barnes_hut(
        gravity=-8000,
        spring_length=350,
        spring_strength=0.02,
        damping=0.5,
    )

    # Concept → colour
    color_map = {
        c: _PALETTE[i % len(_PALETTE)]
        for i, c in enumerate(concepts.keys())
    }

    for node in nodes.values():
        col = color_map.get(node["concept"], _PALETTE[0])
        concept_label = concepts.get(node["concept"], {}).get("label", "?")
        net.add_node(
            node["id"],
            label=node["label"],
            color={
                "background": col["bg"],
                "border": col["border"],
                "highlight": {
                    "background": "white",
                    "border": col["border"],
                },
            },
            shape="dot",
            size=20,
            font={"size": 16, "face": "monospace", "color": "#000"},
            title=f"Concept: {concept_label}",
        )

    for e in display_edges:
        inferred = e.get("inferred", False)
        role_short = local_name(e["role"])
        w = round(e["weight"], 3)
        net.add_edge(
            e["from"],
            e["to"],
            label=f"{role_short}: {w}",
            width=max(1, w * 5),
            color={
                "color": "#cc0000" if inferred else "#333333",
                "highlight": "#555555",
            },
            arrows="to",
            dashes=inferred,
            font={
                "size": 11,
                "face": "monospace",
                "color": "#cc0000" if inferred else "#333333",
                "align": "middle",
            },
            title="inferred" if inferred else "asserted",
        )

    return net


def render_to_html(
    nodes: dict,
    edges: list,
    concepts: dict,
    output_path: str | Path,
    *,
    reasoning: bool = False,
    axioms: list | None = None,
    height: str = "600px",
) -> Path:
    """
    Build the network and write a self-contained HTML file.
    Returns the path that was written.
    """
    net = build_network(
        nodes,
        edges,
        concepts,
        reasoning=reasoning,
        axioms=axioms,
        height=height,
        notebook=False,
    )
    out = Path(output_path)
    net.save_graph(str(out))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Notebook helper – kept here so the CLI/library don't drag IPython in.
# Imported lazily so a missing ``IPython`` install doesn't break the package.
# ─────────────────────────────────────────────────────────────────────────────
def show_in_notebook(
    nodes: dict,
    edges: list,
    concepts: dict,
    *,
    reasoning: bool = False,
    axioms: list | None = None,
    height: str = "600px",
    filename: str = "_amt_graph.html",
) -> None:
    """
    Render the graph and embed it inline (works in classic Notebook,
    JupyterLab and VS Code). Requires ``IPython``.
    """
    from IPython.display import HTML, display  # local import on purpose

    out = render_to_html(
        nodes,
        edges,
        concepts,
        filename,
        reasoning=reasoning,
        axioms=axioms,
        height=height,
    )
    html_content = out.read_text(encoding="utf-8")
    html_escaped = html_content.replace("&", "&amp;").replace('"', "&quot;")
    h = int(height.replace("px", "")) + 20
    display(
        HTML(
            f'<iframe srcdoc="{html_escaped}" '
            f'width="100%" height="{h}px" '
            f'style="border:1px solid #ddd; border-radius:4px;"></iframe>'
        )
    )
