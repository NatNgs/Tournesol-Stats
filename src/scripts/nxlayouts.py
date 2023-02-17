import networkx as nx
import numpy as np

def radialized_layout(G: nx.Graph, full_graph: nx.Graph, pos: dict[str, tuple[float, float]], weight='weight') -> dict[str, tuple[float, float]]:
	if full_graph is None:
		full_graph = G

	# Find center(s) node(s) (higher degrees nodes)
	maxdeg = max(G.degree[node] for node in G.nodes)
	center_nodes = {node for node in G.nodes if G.degree[node] == maxdeg}

	# Compute the distance from every node to the center
	multi_center_nodes = 1 if len(center_nodes) > 1 else 0

	# Location of center
	cntr = (0, 0)
	for node_loc in center_nodes:
		cntr = (cntr[0] + pos[node_loc][0], cntr[1] + pos[node_loc][1])
	cntr = (cntr[0] / len(center_nodes), cntr[1] / len(center_nodes))

	def _inv_weights(node1, node2, data: dict[str, any]):
		if data.get(weight, 0) == 0:
			return None
		return 1/data[weight]

	new_pos = dict() # {node: (rad, ang)}
	for node_loc in G.nodes:
		# Radius: weighted distance to nearest center node
		radius = min([nx.dijkstra_path_length(full_graph, source=centernode, target=node_loc, weight=_inv_weights) for centernode in center_nodes]) + multi_center_nodes

		# Angle: Keep angle from this node to center node (from parameter 'pos')
		angle = _to_polar((pos[node_loc][0] - cntr[0], pos[node_loc][1] - cntr[1]))[1]

		new_pos[node_loc] = _to_carthesian((radius, angle))

	# convert polar coordinates to carthesian
	return new_pos # {node: (x, y)}


def _to_polar(carthesian: tuple[float, float]) -> tuple[float, float]:
	return(np.sqrt(carthesian[0]**2 + carthesian[1]**2), np.arctan2(carthesian[1], carthesian[0]))

def _to_carthesian(polar: tuple[float, float]) -> tuple[float, float]:
	return (np.cos(polar[1])*polar[0], np.sin(polar[1])*polar[0])
