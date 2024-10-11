from typing import Callable
import numpy as np
from numpy._typing import NDArray
import networkx as nx
from numba import jit


@jit(target_backend='cuda', nopython=True)
def gpu_iterate(
		n:int,
		edges:list[float],
		x: NDArray,
		dx: NDArray,
		attraction_factor:float=0.001,
		repulsion_factor:float=0.001,
		repulse_lower_bound:float=0.01,
		repulse_upper_bound:float=np.inf,
		inertia_factor:float=0.25,
		iterations:int=1
	):
	"""
	Args:
		attraction_factor (float, optional): Increased value makes edged attraction force higher. Defaults to 0.001.
		repulsion_factor (float, optional): Increased value makes disconnected edges repulsion higher. Defaults to 0.001.
		repulse_lower_bound (float, optional): Minimum distance between two nodes to be enforced. Defaults to 0.01.
		repulse_upper_bound (float, optional): Maximum distance between two disconnected nodes to apply repulsion force. Defaults to infinity.
		inertia_factor (float, optional): Nodes will keep this factor of their speed between one iteration to the other. Between 0 and 1. Defaults to 0.25.
	"""

	repulse_lower = repulse_lower_bound ** 2
	repulse_upper = repulse_upper_bound ** 2

	for it in range(iterations):
		dx *= inertia_factor

		for i in range(1,n):
			for j in range(0,i):
				desired_d:float = edges[int(j*n+i)]
				if desired_d < 0:
					continue

				vector_ji = np.array((x[i][0]-x[j][0], x[i][1]-x[j][1]))
				current_d2 = vector_ji[0]**2 + vector_ji[1]**2

				# Apply spring force
				if desired_d > 0:
					attraction = attraction_factor * vector_ji * (desired_d - np.sqrt(current_d2))
					dx[i] += attraction
					dx[j] -= attraction

				# Apply repulsion
				elif current_d2 < repulse_upper:
					if current_d2 < repulse_lower: # prevent divide 0
						current_d2 = repulse_lower

					repulsion_x = repulsion_factor * vector_ji[0] / current_d2
					repulsion_y = repulsion_factor * vector_ji[1] / current_d2
					dx[i][0] += repulsion_x
					dx[i][1] += repulsion_y
					dx[j][0] -= repulsion_x
					dx[j][1] -= repulsion_y

		# Apply forces
		x += dx
	return (x, dx)

class ForceLayout():
	"""
	A simple approach to force-directed graph layout.

	self.G: nx.Graph
	self.n: int (number of nodes)
	self.nodes: list(nx.NodeView) ([node1, ...])
	self.x: list[list[int, int]] ([[x, y], ...])
	self.dx: list[list[int, int]] ([[dx, dy], ...])
	"""

	def __init__(self, G: nx.Graph):
		"""
		Args:
			G (nx.Graph): The graph to compute the layout
		"""
		self.G: nx.Graph = G
		self.n: int = 0
		self.nodes: list[str] = []
		self.x: NDArray = np.array([],dtype=(float,float))
		self.dx: NDArray = np.array([],dtype=(float,float))
		self.edges: list[list[float]] = list()


	def update_graph(self,
		pos:dict[str,tuple[float,float]]=None,
		edge_lengths: str | Callable[[str, str, dict[str, any]], float | None]=None,
	):
		"""
		Set or update graph, weights and positions of nodes. To be called after any change in the graph given in constructor

		Args:
			edge_lengths:
				Will act as a desired edge length between nodes
				(if value for an edge is 0, will act as 'distance can be anything', and no force will be applied on these nodes)

				if None (default), then all edges will try to be the same length
				if string, use the corresponding edge data key as desired edge length
				if function(edge) -> float, use this function to compute desired edge length between nodes
					edge: [node1, node2, {prop: val, ...}] (given by nx.Graph.edges.data())

			pos (dict[node,ArrayLike[float]]):
				Initial location of nodes (if none, will be initialized randomly)
		"""
		new_nodes: list[str] = []
		new_x: list[tuple[float,float]] = []
		new_dx: list[tuple[float,float]] = []

		for n in self.G.nodes:
			new_nodes.append(n)
			if n in pos:
				new_x.append(pos[n])
				new_dx.append([0,0])
			elif n in self.nodes:
				i = self.nodes.index(n)
				new_x.append(self.x[i])
				new_dx.append(self.dx[i])
			else:
				new_x.append(np.random.rand(2))
				new_dx.append([0,0])

		self.n = len(new_nodes)
		self.nodes = new_nodes
		self.x = np.array(new_x,dtype=(float,float))
		self.dx = np.array(new_dx,dtype=(float,float))
		self.edges = np.array([0] * ((self.n-1)*self.n))

		# Precompute weights
		for edge in self.G.edges.data():
			w = 0
			if isinstance(edge_lengths, Callable): # provided weight function
				w = edge_lengths(edge)
			elif edge_lengths in edge[2]: # provided weight property's name
				w = edge[2][edge_lengths]
			edge[2]['fdg_d'] = w # save desired distance
			n1 = self.nodes.index(edge[0])
			n2 = self.nodes.index(edge[1])
			if n2 < n1:
				n1,n2 = n2,n1
			self.edges[n1*self.n + n2] = w

	def iterate3(self,
		attraction_factor:float=0.001,
		repulsion_factor:float=0.001,
		repulse_lower_bound:float=0.01,
		repulse_upper_bound:float=np.inf,
		inertia_factor:float=0.25,
		iterations:int=1
	):
		new_x, new_dx = gpu_iterate(
			self.n,
			self.edges,
			self.x,
			self.dx,
			attraction_factor,
			repulsion_factor,
			repulse_lower_bound,
			repulse_upper_bound,
			inertia_factor,
			iterations
		)
		self.x = new_x
		self.dx = new_dx


	def iterate2(self,
		attraction_factor:float=0.001,
		repulsion_factor:float=0.001,
		repulse_lower_bound:float=0.01,
		repulse_upper_bound:float=np.inf,
		inertia_factor:float=0.25,
	):
		"""
		Args:
			attraction_factor (float, optional): Increased value makes edged attraction force higher. Defaults to 0.001.
			repulsion_factor (float, optional): Increased value makes disconnected edges repulsion higher. Defaults to 0.001.
			repulse_lower_bound (float, optional): Minimum distance between two nodes to be enforced. Defaults to 0.01.
			repulse_upper_bound (float, optional): Maximum distance between two disconnected nodes to apply repulsion force. Defaults to infinity.
			inertia_factor (float, optional): Nodes will keep this factor of their speed between one iteration to the other. Between 0 and 1. Defaults to 0.25.
		"""
		self.dx *= inertia_factor

		for i in range(1,self.n):
			ni = self.nodes[i]

			ji = -self.x[0:i] + self.x[i,None]
			dists = np.linalg.norm(ji, axis=1)

			for j in range(0,i):
				nj = self.nodes[j]
				vector_ji = ji[j]
				current_d = dists[j]

				# Apply spring force
				if nj in self.G[ni]:
					desired_d = self.edges[j*self.n + i]
					if not desired_d:
						continue

					attraction = attraction_factor * vector_ji * (desired_d - current_d)
					self.dx[i] += attraction
					self.dx[j] -= attraction

				# Apply repulsion
				elif current_d < repulse_upper_bound:
					if current_d < repulse_lower_bound: # prevent divide 0
						current_d = repulse_lower_bound

					repulsion = repulsion_factor * vector_ji / (current_d*current_d)
					self.dx[i] += repulsion
					self.dx[j] -= repulsion

		# Apply forces
		dabs = np.abs(self.dx)
		self.dx = np.where(dabs > 1, np.sign(self.dx) * np.sqrt(dabs), self.dx)
		self.x += self.dx


	def iterate1(self,
		power=0.001,
		repulse_lower_bound=0.01,
		repulse_upper_bound=np.inf,
		inertia_factor=0.1
	):
		# an array representing the sum of forces on each node.
		# it consists of one force-vector for each node, so it is the same shape as x.
		self.dx *= inertia_factor
		total_tension = 0

		for i in range(1,self.n):
			ni = self.nodes[i]
			for j in range(0,i):
				nj = self.nodes[j]

				if self.G.has_edge(ni, nj):
					# If there is egde from n1 -> nj spring forces will be applied between those nodes
					desired_d = self.G.get_edge_data(ni, nj)['fdg_d']
					if not desired_d:
						continue

					# Spring-like force on each pair of nodes: spring expands or contracts to try to become the right length,
					# so this may be attractive or repulsive.
					# eg for dx[i], if the current distance is too short, then current_d < desired_d,
					# so the middle term is positive,
					# so it is a positive force in the direction of xi_less_xj,
					# that is from xi *away* from xj;
					# and vice versa if the current distance is too long.
					# And mutatis mutandis for dx[j].
					vector_ji = (self.x[i] - self.x[j]) # the vector from xj to xi
					current_d = np.linalg.norm(vector_ji) # distance

					force = power * (desired_d - current_d) * vector_ji
					if current_d + np.linalg.norm(force) < desired_d:
						force += ((desired_d - current_d) * vector_ji)/3
					self.dx[i] += force
					self.dx[j] -= force
					total_tension += np.linalg.norm(force)
				else:
					# No edge between these nodes, apply repulsive force
					vector_ji = (self.x[i] - self.x[j]) # the vector from xj to xi
					current_d2 = sum(vector_ji*vector_ji) # distance

					if current_d2 < repulse_upper_bound*repulse_upper_bound: # Ignore if distance is over higher bound
						if current_d2 < repulse_lower_bound*repulse_lower_bound: # avoid divide-by-zero but still give a nudge
							current_d2 = repulse_lower_bound*repulse_lower_bound

						force = power * vector_ji / current_d2
						self.dx[i] += force
						self.dx[j] -= force
						total_tension += np.linalg.norm(force)

		# Apply forces
		self.x += self.dx
		return np.linalg.norm(self.dx)

	def get_pos(self):
		avg = np.average(self.x, axis=0, keepdims=True)
		res = self.x - avg

		return {n: res[i] for i,n in enumerate(self.nodes)}

	def get_lastiteration_movement(self):
		return np.linalg.norm(self.dx)
