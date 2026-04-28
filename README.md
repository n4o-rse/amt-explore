# amt – Academic Meta Tool, Python edition

A pure-Python port of the [Academic Meta Tool](http://academic-meta-tool.xyz/),
originally written in JavaScript (N3.js + vis.js). Same data model, same fuzzy
logic operators, same export formats — usable from a notebook, from a script,
or as a backend for the existing webviewer.

## Install

```bash
pip install -e .                  # core only
pip install -e ".[notebook]"      # + ipywidgets, pandas, ipython
pip install -e ".[dev]"           # + pytest
```

Requires Python ≥ 3.10. Core dependencies: `rdflib`, `pyvis`.

## Three ways to use it

### 1. As a library

```python
from amt import load_amt, do_reasoning, check_consistency, export_ttl

amt = load_amt("examples/PotterAttributionExample.ttl")

print(len(amt["concepts"]), "concepts,", len(amt["edges"]), "edges")

reasoned = do_reasoning(amt["edges"], amt["axioms"])
ok, violations = check_consistency(amt["edges"], amt["axioms"])

ttl = export_ttl(
    amt["nodes"], amt["edges"], amt["concepts"], amt["roles"],
    amt["axioms"], rdf_graph=amt["graph"], prefix=amt["prefix"],
    with_reasoning=True,
)
```

### 2. From the command line

```bash
amt examples/PotterAttributionExample.ttl --info --check
amt examples/PotterAttributionExample.ttl --reason \
    --export-ttl    out/potter.ttl     \
    --export-cypher out/potter.cypher  \
    --export-html   out/potter.html
```

`amt --help` lists every flag.

### 3. Feeding the bundled webviewer

The `docs/` folder contains the original JavaScript webviewer. Run a
Python export to `docs/data/`, then point the viewer at it via URL
parameter:

```bash
amt examples/PotterAttributionExample.ttl --reason \
    --export-ttl docs/data/my-export.ttl
cd docs && python -m http.server 8000
# open http://localhost:8000/index.htm?ttl=data/my-export.ttl
```

The same setup works as a **GitHub Pages site** — enable Pages with
source `main` / folder `/docs` in the repository settings. See
[`INTEGRATION.md`](INTEGRATION.md) for details.

## Notebook

The notebook in `notebooks/amt-explore.ipynb` is now a thin wrapper around the
library — upload widget, dataframes for inspection, inline pyvis graph,
exporters. All the engine code lives in `amt/`.

## Layout

```
amt/
├── core.py        load_amt, do_reasoning, check_consistency
├── viz.py         build_network, render_to_html, show_in_notebook
├── export.py      export_ttl, export_cypher
└── cli.py         the `amt` command

docs/              JS webviewer (GitHub Pages source)
tests/             pytest smoke tests using the Potter example
notebooks/         interactive exploration
examples/          sample TTL files (Potter Attribution)
INTEGRATION.md     how Python exports plug into the webviewer
```

## What was ported from the JS side

| JS source            | Python module    |
|----------------------|------------------|
| `amt.js`             | `amt/core.py`    |
| `amt-render.js`      | `amt/viz.py`     |
| `amt-export.js`      | `amt/export.py`  |

Everything is round-trip-compatible with the JS tool: a TTL written by
`export_ttl` can be opened in the webviewer, and a TTL written by the
webviewer can be loaded with `load_amt`.

## License

MIT (same as the parent project).
