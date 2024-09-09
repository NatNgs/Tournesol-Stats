# Imports
import math
import time
import requests
import itertools
import networkx as nx
from typing import Iterable
from matplotlib import pyplot

# Types
Eid = str

# Functions
def compute_elevation(elm1, elm2, ancest_cache):
	ba1:set = ancest_cache[elm1][0]
	ba2:set = ancest_cache[elm2][0]
	bd1:set = ancest_cache[elm1][1]
	bd2:set = ancest_cache[elm2][1]
	inter:set = ba1.intersection(ba2).union(bd1.intersection(bd2))

	# PART 1
	elev12 = len(bd2.difference(bd1)) + len(ba1.difference(ba2)) +2
	for n in ba1.difference(inter):
		elev12 += len(bd2.difference(ancest_cache[n][1]))+1
	for n in bd1.difference(inter):
		elev12 += len(ba1.difference(ancest_cache[n][0]))+1

	# PART 2
	elev21 = len(ba2.difference(ba1)) + len(bd1.difference(bd2)) +2
	for n in ba2.difference(inter):
		elev21 += len(bd1.difference(ancest_cache[n][1]))+1
	for n in bd1.difference(inter):
		elev21 += len(ba2.difference(ancest_cache[n][0]))+1

	return (elev12, elev21)

last_tnsl_call=time.time()
def callTournesol(path: str, JWT:str):
	global last_tnsl_call
	BASE_URL='https://api.tournesol.app/'
	wait=(1-(time.time()-last_tnsl_call))
	if wait > 0:
		time.sleep(wait)
	print(' ~', BASE_URL + path)
	response = requests.get(BASE_URL + path, headers={
		'Authorization': JWT
	})
	last_tnsl_call = time.time()
	return response.json()

def callTournesolMultiReversed(path:str, JWT:str, args:str=None) -> Iterable[dict]:
	LIMIT=1000

	# Get the first page to get the total number
	URL=f'{path}?limit={LIMIT}' + (('&' + args) if args else '')
	rs = callTournesol(URL, JWT)
	resultspage1 = rs['results']
	pages=math.ceil(rs['count']/LIMIT)

	for page in range(pages-1, 0, -1):
		offset = LIMIT*page
		rs = callTournesol(URL + f'&offset={offset}', JWT)
		for r in reversed(rs['results']):
			yield r

	for r in reversed(resultspage1):
		yield r

# Classes
class CmpGraph():
	def __init__(self):
		self.G = nx.DiGraph() # Directed graph, from low recom to high recom
		self.comparisons:list[Eid] = [] # From oldest (first) to newest (last)

	def reset(self):
		self.comparisons.clear()
		self.G.clear()

	def add_evaluation(self, elm1:Eid, elm2:Eid): # such as elm2 > elm1
		has_removed = False
		if elm1 in self.G and elm2 in self.G:
			has_removed = self._remove_old_nodes(elm1, elm2)

		# Add the new comparison
		self.comparisons.append((elm1, elm2))
		self.G.add_edge(elm1, elm2)
		return has_removed

	def add_evaluations(self, elms:Iterable[Eid]):
		lastprint_tm = time.time()
		for i,new_cmp in enumerate(elms):
			self.add_evaluation(new_cmp[0], new_cmp[1])
			tm = time.time()
			if tm - lastprint_tm > 2:
				print('Adding comparisons -', i)
				lastprint_tm = time.time()

	def _remove_old_nodes(self, elm1, elm2):
		path_from_2_to_1 = list(nx.all_simple_paths(self.G, elm2, elm1)) # if not empty, means there is a series of comparisons telling that elm2 > elm1

		if not path_from_2_to_1:
			return False

		# Told that elm2 should be better than elm1, but ancient comparisons tell that elm1 > elm2; need to remove old comparisons until it resolves the conflict
		# Try to remove them from the oldest to the most recent until it resolves

		# Find all pairs of nodes in all paths between 2 to 1
		allpairs_inpath = list() # [(elm2, x3), (x3, x4), (x4, elm1), (elm2, x5), (x5, elm1), ...]
		for path in map(nx.utils.pairwise, path_from_2_to_1):
			for pair in path:
				if pair not in allpairs_inpath:
					allpairs_inpath.append(pair)

		# Sort by oldest to most recent
		allpairs_inpath.sort(key=lambda p: self.comparisons.index(p))

		# Find what nodes to remove, oldest (first priority), then the fewest possible (second priority)
		for maxindex in range(0,len(allpairs_inpath)):
			for num in range(1, maxindex+1):
				for torm in itertools.combinations(allpairs_inpath[:maxindex], num):
					newgraph = self.G.copy()
					newgraph.remove_edges_from(torm)
					if not nx.has_path(newgraph, elm2, elm1):
						# Found a set of old comparisons to remove to resolve the conflict
						for pair in torm:
							print(f"Removed comparison: {pair[1]} > {pair[0]} (oldest {len(self.comparisons)-self.comparisons.index(pair)}/{len(self.comparisons)} cmps)")
							self.comparisons.remove(pair)
						self.G.remove_edges_from(torm)
						return True

		if nx.has_path(self.G, elm2, elm1):
			raise('!!! ERROR: A path still exists from', elm2, 'to', elm1, 'after resolution !!!')

	def recommand_comparison(self):
		# For printing progress
		nbpairs = 0
		lastprint_tm = time.time()

		bestpairs:list[tuple[tuple[Eid,Eid],tuple[int,int]]] = list() # ((str1, str2), (elev+, elev-))

		# Cache
		ancest_cache = {n:(nx.ancestors(self.G, n), nx.descendants(self.G, n)) for n in self.G}

		# Generator of pairs
		nodes_to_pair = [n for n in self.G if self.G.degree(n) < 10]
		pairs = (
			(pair, compute_elevation(pair[0], pair[1], ancest_cache))
			for pair in itertools.combinations(nodes_to_pair, 2)
			if not(pair[0] in ancest_cache[pair[1]][0]
				or pair[0] in ancest_cache[pair[0]][0])
		)

		for pair in pairs:
			nbpairs += 1

			if not bestpairs:
				bestpairs.append(pair)
				continue

			if nbpairs % 1000 == 0:
				tm = time.time()
				if tm - lastprint_tm > 5:
					print(f"Fetching pairs... - {nbpairs/1000:.0f}k", bestpairs)
					lastprint_tm = tm

			if pair[1] == bestpairs[0][1]:
				# Same
				bestpairs.append(pair)
			elif (min(pair[1]) > min(bestpairs[0][1])
				or min(pair[1]) == min(bestpairs[0][1]) and max(pair[1]) > max(bestpairs[0][1])
			): # Better
				bestpairs.clear()
				bestpairs.append(pair)
		return bestpairs

	def draw(self, outputfile:str):
		fig = pyplot.figure(figsize=(20,10))
		ax = fig.add_subplot()

		# Compute nodes location
		ttl = self.G.number_of_nodes()
		_pos:dict[str,tuple[int,int]] = dict() # {n: (x,y)}
		xy=[]
		xx=[]
		yy=[]
		ss=[]
		cc=[]
		mind=None
		maxd=None
		for n in self.G:
			anc = len(nx.ancestors(self.G, n))
			dec = len(nx.descendants(self.G, n))

			x = anc-dec
			y = anc+dec
			_pos[n] = (x/ttl,y/ttl)

			if not mind or x < _pos[mind][0]:
				mind = n
			if not maxd or x > _pos[maxd][0]:
				maxd = n

			if _pos[n] in xy:
				ss[xy.index(_pos[n])] += 1
			else:
				xy.append(_pos[n])
				xx.append(x/ttl)
				yy.append(y/ttl)
				ss.append(1)
				r = int(256* ((ttl-x)/2) /ttl)
				g = int(256* ((ttl+x)/2) /ttl)
				b = int(256* ((ttl-y))   /ttl)
				cc.append(f"#{r:02X}{g:02X}{b:02X}")

		print('Preparing graph...')

		# Print connexions from min to max node
		if nx.has_path(self.G, mind, maxd):
			path_min_to_max = nx.shortest_path(self.G, source=mind, target=maxd)
			l_x=[]
			l_y=[]
			for i in path_min_to_max:
				l_x.append(_pos[i][0])
				l_y.append(_pos[i][1])
			ax.plot(l_x, l_y, color='#000')

		# Print nodes on top
		ax.scatter(x=xx, y=yy, s=ss, c=cc)
		ax.set_xlim(-1, 1)
		ax.set_ylim(0, 1)
		fig.savefig(outputfile, bbox_inches='tight')
		print('Figure saved as', outputfile)

def tournesol_to_pair(tournesol_comparison:dict):
	ea = tournesol_comparison['entity_a']['uid']
	eb = tournesol_comparison['entity_b']['uid']
	score = [x for x in tournesol_comparison['criteria_scores'] if x['criteria'] == 'largely_recommended'][0]['score']
	return None if score == 0 else ((ea,eb) if score > 0 else (eb,ea))

# Main
def __main__():
	cmpgrph = CmpGraph()

	# Fetch comparisons
	JWT='Bearer 0qo5cfCZACuvMSMbDGAuJYf6GXKfBi'
	cmpgrph.add_evaluations(
		filter(None,
			map(tournesol_to_pair,
				callTournesolMultiReversed('users/me/comparisons/videos', JWT)
			)
		)
	)
	cmpgrph.draw('output/elevations_NatNgs.svg')

	bstcmp = cmpgrph.recommand_comparison()[0]
	print(f"https://tournesol.app/comparison?uidA={bstcmp[0][0]}&uidB={bstcmp[0][1]} {bstcmp[1]}")



if __name__ == '__main__':
	__main__()
