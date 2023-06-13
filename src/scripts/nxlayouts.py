import random
import networkx as nx
import numpy as np

def radialized_layout(G: nx.Graph, pos: dict[str, tuple[float, float]] = dict(), full_graph: nx.Graph = None, weight='weight') -> dict[str, tuple[float, float]]:
	if full_graph is None:
		full_graph = G

	new_pos = dict() # {node: (rad, ang)}
	for n in G.nodes:
		if not n in pos:
			new_pos[n] = np.array([random.random()*2-1, random.random()*2-1])
		else:
			new_pos[n] = np.array(pos[n])

	# Find center(s) node(s) (higher degrees nodes)
	maxdeg = max(G.degree[node] for node in G.nodes)
	center_nodes = {node for node in G.nodes if G.degree[node] == maxdeg}
	center_nodes_ln = len(center_nodes)

	# Compute the distance from every node to the center
	multi_center_nodes = 1 if center_nodes_ln > 1 else 0

	# Location of center
	cntr = np.array([0.0, 0.0])
	for node_loc in center_nodes:
		cntr += new_pos[node_loc]
	cntr /= center_nodes_ln

	def _inv_weights(node1, node2, data: dict[str, any]):
		if data.get(weight, 0) == 0:
			return None
		return 1/data[weight]
	_weight=None if weight == None else _inv_weights

	radii: list[dict[str,float]] = []
	for cn in center_nodes:
		radii.append(nx.shortest_path_length(full_graph, source=cn, weight=_weight))

	for node_loc in G.nodes:
		# Radius: weighted distance to nearest center node
		radius = min(r.get(node_loc, 99999) for r in radii) + multi_center_nodes

		# Angle: Keep angle from this node to center node (from parameter 'pos')
		angle = _get_polar_angle(new_pos[node_loc] - cntr)

		# convert polar coordinates to carthesian
		new_pos[node_loc] = _to_carthesian(radius, angle)

	return new_pos # {node: (x, y)}


def _get_polar_angle(carthesian: np.ndarray) -> np.ndarray:
	return np.arctan2(carthesian[1], carthesian[0])

def _to_carthesian(radius, angle) -> np.ndarray:
	return (np.cos(angle)*radius, np.sin(angle)*radius)
