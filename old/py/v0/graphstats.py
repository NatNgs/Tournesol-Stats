import sys
import time
import pandas as pd

###
###
### DATA STRUCTURE
###
###

class Graph:
	def __init__(self):
		self.users = dict() # { uname: User }
		self.nodes = dict() # { vid: Node }

	def add_user(self, username, weight):
		self.users[username] = User(username, weight)

	def add_link(self, username, vid1, vid2):
		if not (vid1 in self.nodes):
			self.nodes[vid1] = Node(vid1)
		if not (vid2 in self.nodes):
			self.nodes[vid2] = Node(vid2)

		node1 = self.nodes[vid1]
		node2 = self.nodes[vid2]
		if not (node2 in node1.links): # Link not yet defined
			link = Link(node1, node2)
			node1.links[node2] = link
			node2.links[node1] = link

		link = node1.links[node2]
		link.evaluated_by.add(self.users[username])
		link.recompute()

	def recompute(self):
		# Reset all nodes
		for n in self.nodes.values():
			n.dists = None

		# Pick a random node
		for node in self.nodes.values():
			# Mark all nodes as not yet discovered
			for n in self.nodes.values():
				n.discovered = False
			# Explore the node
			node.dists = node.explore()

	def clear_disconnected(self):
		self.nodes = {vid: self.nodes[vid] for vid in self.nodes if len(self.nodes[vid].links) < 1}

class User:
	def __init__(self, username, ratio):
		self.name = username
		self.ratio = float(1+ratio)

	def __str__(self):
		return 'u:' + (f'"{self.name}"' if self.name.isnumeric() else self.name) + f":{self.ratio:0.2f}"

	def __hash__(self):
		return hash(self.name)
	def __eq__(self, other):
		if not isinstance(other, type(self)): return NotImplemented
		return self.name == other.name

class Node:
	def __init__(self, vid):
		self.id = vid
		self.links = dict() # { Node: Link }
		self.discovered = False
		self.dists = None

	def explore(self):
		# Init with dists=0
		dists = [set(self.links.keys())]
		visited = set(self.links.keys())

		# Dists > 1
		dist = 0
		while len(dists[dist]) > 0:
			dist = dist+1
			dists.append(set())
			for node in dists[dist-1]:
				for subnode in node.links.keys():
					if not(subnode in visited):
						visited.add(subnode)
						dists[dist].add(subnode)

		dists.pop(dist) # Last is empty, remove-it

		return list(map(len, dists))

	def __str__(self):
		if self.dists is None:
			return f"<{self.id}, undiscovered>"
		else:
			return f"<{self.id}, {self.dists}>"

	def __hash__(self):
		return hash(self.id)
	def __eq__(self, other):
		if not isinstance(other, type(self)): return NotImplemented
		return self.id == other.id

class Link:
	def __init__(self, node1, node2):
		self.node1 = node1
		self.node2 = node2
		self.evaluated_by = set() # { User, ... }
		self.cached = 0

	def recompute(self):
		self.cached = sum([u.ratio for u in self.evaluated_by])

	def __hash__(self):
		return hash((self.node1, self.node2))
	def __eq__(self, other):
		if not isinstance(other, type(self)): return NotImplemented
		return self.node1 == other.node1 and self.node2 == other.node2

###
###
### PARSING
###
###

def unload_user_data(datafolder, graph):
	# public_username,trust_score
	cmpFile = open(datafolder + 'users.csv', 'r', encoding='utf-8')

	# Skip first line (headers)
	cmpFile.readline()

	while True:
		line = cmpFile.readline()

		# if line is empty, end of file is reached
		if not line:
			break

		ldata = line.strip().split(',')
		graph.add_user(ldata[0], 0 if ldata[1] == '' else float(ldata[1]))

def unload_comparison_data(datafolder, graph, criteria):
	# public_username,video_a,video_b,criteria,weight,score
	cmpFile = open(datafolder + 'comparisons.csv', 'r', encoding='utf-8')

	# Skip first line (headers)
	cmpFile.readline()

	while True:
		line = cmpFile.readline()

		# if line is empty, end of file is reached
		if not line:
			break

		ldata = line.split(',')
		if ldata[0] == 'NatNgs' and ldata[3] == criteria:
			graph.add_link(ldata[0], ldata[1], ldata[2])

def main():
	# Read input file
	datafolder = sys.argv[1] + '/'
	criteria = 'largely_recommended' if len(sys.argv) <= 2 else sys.argv[2]

	graph = Graph()
	print('Parsing user data...')
	t = time.perf_counter()
	unload_user_data(datafolder, graph)
	t = time.perf_counter() - t
	print(f'Done ({t:0.4f}s) - {len(graph.users)} users')

	print('Parsing comparison data...')
	t = time.perf_counter()
	unload_comparison_data(datafolder, graph, criteria)
	t = time.perf_counter() - t
	print(f'Done ({t:0.4f}s) - {len(graph.nodes)} nodes')

	print('Computing...')
	t = time.perf_counter()
	graph.recompute()
	t = time.perf_counter() - t
	print(f'Done ({t:0.4f}s) - {len(graph.nodes)} nodes')

# Exec
if __name__ == "__main__":
	main()
