import random
import time
import itertools
import numpy as np
import networkx as nx

def radialized_layout(
		G: nx.Graph,
		pos: dict[str, tuple[float, float]] = dict(),
		full_graph: nx.Graph = None,
		weight='weight',
		center_nodes:list[str] = None) -> dict[str, tuple[float, float]]:

	if full_graph is None:
		full_graph = G

	new_pos = dict() # {node: (rad, ang)}
	for n in G.nodes:
		new_pos[n] = np.array(pos[n]) if n in pos else np.array([random.random()*2-1, random.random()*2-1])

	# Find center(s) node(s) (higher degrees nodes)
	if not center_nodes:
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


def springy_topological_layout(
		G: nx.DiGraph,
		pos: dict[str, tuple[float, float]] = dict(),
		iterations:int = 100,
		force_spring_y:float = 0.9,
		force_attract_x:float = 0.5,
		force_magnet:float = 0.8,
		over_blounds_value:float = 0,
		weight='weight') -> dict[str, tuple[float, float]]:
	'''
	Updates pos such as:
	- Nodes are sorted from top to bottom according to their topological rank (when there is a link from A to B, A will try to be located above B)
		- [Bottom nodes] Nodes with only exiting edges (from them to others) are drawn all at the same level, on the bottom of the diagram
		- [Top nodes] Nodes with only entering edges (from others to them) are drawn all at the same level, on the top of the diagram
	- Vertical distance from linked nodes is relative to the weight of the edges applying to them
	- Horizontal distances from every node is such as the nodes are not too close to eachother

	At every iteration:
	1- Move nodes vertically depending on their topological rank
	2- Move nodes horizontally depending on their edges
	3- Apply collision force (for nodes too close to eachother), magnet attractive force (for nodes near eachother) and magnet pull force (for nodes far from eachother).
		Will apply only the strongest force on each node (only the closest node will act on a given one)
	'''

	t=time.time()
	DEBUG_PRINT_FREQ=2.5 # seconds
	MIN_DIST = 1/G.number_of_nodes() # Minimum distance between nodes: Distance from node to node if we put them in a single line across the board

	# Precompute weights
	_weights:dict[str,dict[str,float]] = {n:{} for n in G.nodes}
	for n in G.nodes:
		for m in G[n]:
			_weights[n][m] = 1 if weight is None else G[n][m].get(weight, 1)
			if n not in _weights[m]:
				_weights[m][n] = 1 if weight is None else G[n][m].get(weight, 1)


	nodes_x:dict[str,float] = {n: pos.get(n, (i*MIN_DIST,None))[0] for i,n in enumerate(G.nodes)}
	nodes_y:dict[str,float] = {}
	moving_nodes_y:set[str] = set()

	# Detect Moving and Fixed nodes
	for n in G.nodes:
		if sum(_weights[n].values()) == 0:
			nodes_y[n] = pos.get(n, (0.5,0.5))[1] # Node is not connected: put it to the middle of the graph
		elif not any(G.predecessors(n)):
			nodes_y[n] = 0 - over_blounds_value*len(list(G.successors(n)))
		elif not any(G.successors(n)):
			nodes_y[n] = 1 + over_blounds_value*len(list(G.predecessors(n)))
		else:
			moving_nodes_y.add(n)
			nodes_y[n] = pos.get(n, (0.5,0.5))[1] # Moving nodes are initialized to their current location (or to the middle if no 'pos' provided)

	# ----------------- #
	## --- Iterate --- ##

	for i in range(iterations):
		if time.time() - t > DEBUG_PRINT_FREQ:
			print(f'[Running Springy Topological Layout] {i}/{iterations}')
			t += DEBUG_PRINT_FREQ

		# -- Apply Vertical springs -- #
		_upd_nodes_y:dict[str,float] = {}
		for n in moving_nodes_y:
			# New location y is the average between the 3 following values:
			# - average y location of all other nodes connected in both sides from and to this node
			# - highest y location from all nodes connected to this node
			# - lowest y location from all nodes connected from this node
			nodes_in = set(G.predecessors(n))
			nodes_out = set(G.successors(n))
			nodes_zero = nodes_in.intersection(nodes_out)
			nodes_in.difference_update(nodes_zero)
			nodes_out.difference_update(nodes_zero)

			vals = []
			if nodes_zero:
				vals.append(sum(nodes_y[m]*_weights[n][m] for m in nodes_zero)/sum(_weights[n][m] for m in nodes_zero))
			if nodes_in:
				vals.append(sum(nodes_y[m]*_weights[m][n] for m in nodes_in)/sum(_weights[m][n] for m in nodes_in))
			if nodes_out:
				vals.append(sum(nodes_y[m]*_weights[n][m] for m in nodes_out)/sum(_weights[n][m] for m in nodes_out))
			if vals:
				newy = sum(vals)/len(vals)
				_upd_nodes_y[n] = nodes_y[n]*(1-force_spring_y) + newy*force_spring_y
		nodes_y.update(_upd_nodes_y)

		# -- Apply Horizontal attraction -- #
		# Move all nodes toward their linked edges (to minimize horizontal distance), according to the weights multiplied by the y distance between the two
		_upd_nodes_x:dict[str,float] = {}
		for n in G.nodes:
			w = sum(_weights[n][m]*abs(nodes_y[m]-nodes_y[n]) for m in _weights[n])
			if w == 0:
				_upd_nodes_x[n] = nodes_x[n]
			else:
				newx = sum(nodes_x[m]*_weights[n][m]*abs(nodes_y[m]-nodes_y[n]) for m in _weights[n]) / w
				_upd_nodes_x[n] = nodes_x[n]*(1-force_attract_x) + newx*force_attract_x

		# Normalize x locations to be within 0-1 range, and apply update
		_minx = min(_upd_nodes_x.values())
		_maxx = max(_upd_nodes_x.values())
		nodes_x = {n: (v-_minx)/(_maxx-_minx) for n,v in _upd_nodes_x.items()}

		# -- Apply Repulsive force on x and y -- #
		# If nodes are too close (less than MIN_DIST distance): move them away from eachother just enough to separate them by MIN_DIST (and apply force_repulse_xy to reduce the movement)
		_debounced_locations_x:dict[str,list[float]] = {n:[0] for n in G.nodes}
		_debounced_locations_y:dict[str,list[float]] = {n:[0] for n in moving_nodes_y}
		for n1,n2 in itertools.combinations(G.nodes, 2):
			d2 = (nodes_x[n1]-nodes_x[n2])**2 + (nodes_y[n1]-nodes_y[n2])**2
			if d2 == 0:
				# Nodes are exactly at the same location: apply hard colision on them, moving one to the left, the other to the right by half MIN_DIST
				_debounced_locations_x[n1].append(-MIN_DIST/2)
				_debounced_locations_x[n2].append(+MIN_DIST/2)
			else:
				upd_d = MIN_DIST**2 - d2
				# if upd_d > 0:	# Nodes are too close to eachother: apply colision to them
				if upd_d <= 0:
					if d2 > 3*(MIN_DIST**2):
						# Apply gravity for nodes that are far away
						upd_d = -force_magnet * (MIN_DIST**2) / d2
					else:
						# Nodes are close but not colliding: apply small repulsive force between them
						upd_d = force_magnet * (MIN_DIST**2) / d2

				# Compute the angle between both nodes location, and move them appart by upd_d
				angle = _get_polar_angle(np.array([nodes_x[n1]-nodes_x[n2], nodes_y[n1]-nodes_y[n2]]))
				_c,_s = upd_d*np.cos(angle),upd_d*np.sin(angle)
				_debounced_locations_x[n1] -= _c
				_debounced_locations_x[n2] += _c
				if n1 not in moving_nodes_y:
					if n2 in moving_nodes_y:
						_debounced_locations_y[n2].append(2*_s)
				elif n2 not in moving_nodes_y:
					_debounced_locations_y[n1].append(-2*_s)
				else:
					_debounced_locations_y[n1].append(-_s)
					_debounced_locations_y[n2].append(+_s)
		nodes_x = {n: nodes_x[n]+max(_debounced_locations_x[n], key=abs) for n in G.nodes}
		nodes_y = {n: nodes_y[n]+(max(_debounced_locations_y[n], key=abs) if n in moving_nodes_y else 0) for n in G.nodes}

	# Combine nodes_x and nodes_y and outputs new pos
	return {n: (nodes_x[n], nodes_y[n]) for n in G.nodes}



# ---------------------------------------

###########
## UTILS ##
###########

def _get_polar_angle(carthesian: np.ndarray) -> np.ndarray:
	return np.arctan2(carthesian[1], carthesian[0])

def _to_carthesian(radius, angle) -> np.ndarray:
	return (np.cos(angle)*radius, np.sin(angle)*radius)
