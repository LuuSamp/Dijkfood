
import osmnx as ox

_DEFAULT_PLACE = "São Paulo, SP, Brazil"
_DEFAULT_NETWORK = "drive"

ox.save_graphml(ox.graph_from_place(_DEFAULT_PLACE, network_type=_DEFAULT_NETWORK), "sp.graphml")