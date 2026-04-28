"""
Academic Meta Tool – Python edition.

A pure-Python port of http://academic-meta-tool.xyz/ (originally JavaScript:
N3.js + vis.js). Designed to be used three ways from the same code base:

1. **As a library** – ``from amt import load_amt, do_reasoning, export_ttl``
2. **From the command line** – ``amt input.ttl --reason --export-ttl out.ttl``
3. **Feeding the existing webviewer** – CLI writes a TTL, the JS viewer in
   ``docs/`` loads it.

See the ``README.md`` for examples.
"""
from .core import (
    AMT,
    check_consistency,
    do_reasoning,
    load_amt,
    local_name,
)
from .export import (
    export_cypher,
    export_ttl,
    write_cypher,
    write_ttl,
)
from .viz import (
    build_network,
    render_to_html,
    show_in_notebook,
)

__version__ = "0.1.0"

__all__ = [
    # core
    "AMT",
    "load_amt",
    "do_reasoning",
    "check_consistency",
    "local_name",
    # export
    "export_ttl",
    "export_cypher",
    "write_ttl",
    "write_cypher",
    # viz
    "build_network",
    "render_to_html",
    "show_in_notebook",
    # meta
    "__version__",
]
