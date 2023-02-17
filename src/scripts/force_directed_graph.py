from typing import Callable
import numpy as np
import networkx as nx

"""A module to demonstrate a force-directed graph layout algorithm.
This implementation is done using GraphX.
"""

class ForceLayout():
	def __init__(self,
		G: nx.Graph,
		weight: str or Callable[[str, str, dict[str, any]], float or None]=None,
		pos=None
	):
		"""A simple approach to force-directed graph layout.

		G:
			a graph, optionally with edge length values
		weight:
			Will act as a desired edge length between nodes
			(if value for an edge is 0, will act as 'distance can be anything', and no force will be applied on these nodes)

			if None (default), then all edges will try to be the same length
			if string, use the corresponding edge data key as desired edge length
			if function(edge) -> float, use this function to compute desired edge length between nodes
				edge: [node1, node2, {prop: val, ...}] (given by nx.Graph.edges.data())
		pos:
			Initial location of nodes (if none, will be initialized randomly)
		"""
		self.G = G
		self.n = G.number_of_nodes()
		self.nodes = sorted(G.nodes()) # need a fixed ordering of nodes

		# output position
		if pos:
			self.x = [np.array(pos[node]) for node in self.nodes]
		else:
			self.x = np.random.random((self.n, 2)) # randomly initialise positions

		# Precompute weights
		for edge in G.edges.data():
			w = 0
			if isinstance(weight, Callable): # provided weight function
				w = weight(edge)
			elif weight in edge[2]: # provided weight property's name
				w = edge[weight]
			edge[2]['fdg_d'] = w # save desired distance squared

		# Inertia
		self.dx = np.zeros((self.n,2))

	def iterate(self,
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

		# the key line: move x according to the summed forces dx
		self.x += self.dx
		return [np.linalg.norm(self.dx), total_tension]

	def get_pos(self):
		return {self.nodes[i]: self.x[i] for i in range(len(self.nodes))}
