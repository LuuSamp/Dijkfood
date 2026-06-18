"""Download São Paulo OSM street graph as GraphML for local routing development."""

from __future__ import annotations

import argparse
from pathlib import Path

import osmnx as ox

_DEFAULT_PLACE = "São Paulo, SP, Brazil"
_DEFAULT_NETWORK = "drive"
_DEFAULT_OUTPUT = Path("sp.graphml")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download OSM graph for local routing tests")
    parser.add_argument("--place", default=_DEFAULT_PLACE, help="OSMnx place query")
    parser.add_argument(
        "--network-type",
        default=_DEFAULT_NETWORK,
        help="OSMnx network type (default: drive)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output GraphML path (default: sp.graphml in cwd)",
    )
    args = parser.parse_args()

    graph = ox.graph_from_place(args.place, network_type=args.network_type)
    ox.save_graphml(graph, args.output)
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
