import math
import warnings
import matplotlib.pyplot as plt
import networkx as nx
import time

import numpy as np

from model.comparisons import ComparisonFile, ComparisonLine
from model.video import Video
from scripts.nxlayouts import radialized_layout
from scripts.force_directed_graph import ForceLayout

def build_graph(input_dir: str, target_user: str):
	graph = nx.Graph()
	comparisons = ComparisonFile(input_dir)

	users_data:dict[str, int] = dict()
	def __fetch_usercmpscount(ldata: ComparisonLine):
		if not ldata.user in users_data:
			users_data[ldata.user] = 1
		else:
			users_data[ldata.user] = users_data[ldata.user] + 1
	comparisons.foreach(__fetch_usercmpscount)

	# Exclude users with not enough comparisons
	other_users = {uid for uid in users_data if users_data[uid] > 2}
	if not target_user in other_users:
		other_users.add(target_user)

	# Parsing comparison data
	criteria = 'largely_recommended'
	def __unload_comparison_data(ldata: ComparisonLine):
		if ldata.criteria != criteria or ldata.user not in other_users:
			return

		if not graph.has_edge(ldata.vid1, ldata.vid2):
			graph.add_edge(ldata.vid1, ldata.vid2, cmps=0, cmp_by_me=False)

		edge = graph.get_edge_data(ldata.vid1, ldata.vid2, None)
		edge['cmps'] = edge['cmps']+1

		if ldata.user == target_user:
			edge['cmp_by_me'] = True

	comparisons.foreach(__unload_comparison_data)

	return graph



def add_recommended_nodes(graph: nx.Graph, videos: dict[str, Video]):
	# Keep only nodes compared by me
	keep_nodes = set()
	for edge in graph.edges.data():
		if edge[2]['cmp_by_me']:
			keep_nodes.add(edge[0])
			keep_nodes.add(edge[1])

	# Exclude from search nodes with too many connexions (most of the time will not be in furthest, and reduces a lot time to compute)
	nodes_degree = [(node, graph.degree(node, None)) for node in graph.nodes if node in keep_nodes]
	aggregated = list()
	for pair in nodes_degree:
		while len(aggregated) < pair[1]:
			aggregated.append(0)
		aggregated[pair[1]-1] = aggregated[pair[1]-1] + 1

	# Keeping minimum 80% of the nodes, from lowest degree (note that 80% is magic number, but do the job pretty well)
	max_degree_to_keep = 1
	target_count = len(nodes_degree) * .8
	while sum(aggregated[:max_degree_to_keep]) < target_count:
		max_degree_to_keep = max_degree_to_keep + 1
	max_degree_to_keep = max_degree_to_keep + 1
	print('Ignoring', sum(aggregated[max_degree_to_keep:]), 'nodes having degree between', max_degree_to_keep, 'and', len(aggregated), end=' ')
	nodes = [node for (node, degree) in nodes_degree if degree <= max_degree_to_keep]
	print(f"(ignoring {len(nodes_degree)*(len(nodes_degree)-1) - len(nodes)*(len(nodes)-1)}/{len(nodes_degree)*(len(nodes_degree)-1)} ({(len(nodes_degree)*(len(nodes_degree)-1) - len(nodes)*(len(nodes)-1))/(len(nodes_degree)*(len(nodes_degree)-1)):0.1%}) operations)")

	max_max_min = 0
	paths = []
	for node1 in nodes:
		shrt_paths = dict() # {target: shortestpath}
		for node2 in nodes:
			shrt_paths[node2] = nx.shortest_path_length(graph, node1, node2, weight=None)

		max_min = max(shrt_paths.values())
		if max_min > max_max_min:
			paths = []
			max_max_min = max_min

		if max_min == max_max_min:
			for node2 in shrt_paths:
				if node2 in nodes and node2 > node1 and shrt_paths[node2] == max_min:
					paths.append((node1, node2))

	print('Maximum distance =', max_max_min)
	# Sort by 1: max degree, 2: sum of degrees
	paths.sort(key=lambda pair: (
		max(graph.degree(pair[0]), graph.degree(pair[1])),
		graph.degree(pair[0]) + graph.degree(pair[1])
	))

	print('\nRecommending:')
	already_relinked = set()
	for path in paths:
		if not (path[0] in already_relinked or path[1] in already_relinked):
			print(f"{videos[path[0]]}\n{videos[path[1]]}\n")
			already_relinked.add(path[0])
			already_relinked.add(path[1])
			graph.add_edge(path[0], path[1], cmps=0, cmp_by_me=False)



def __make_subgraph(graph: nx.Graph):
	vids_to_show = set()
	for edge in graph.edges.data():
		if edge[2]['cmp_by_me']:
			vids_to_show.add(edge[0])
			vids_to_show.add(edge[1])
	return nx.subgraph_view(graph, filter_node=lambda node: node in vids_to_show)

def draw_graph_to_file(graph: nx.Graph, videos: dict[str, Video], filename: str):
	print('Graphing...')

	# Keep unwanted nodes
	subgraph: nx.Graph = __make_subgraph(graph)

	def _inv_weights(edge: dict[str, any]) -> float:
		val = edge[2].get('cmps', 0)
		if val == 0:
			return None
		return 1/val

	def _prepare_image():
		# Prepare graph
		plt.box(False)
		plt.clf()
		plt.tight_layout()
		plt.rc('axes', unicode_minus=False)

		return plt.figure(figsize=(10, 10), frameon=False)

	def _do_graph(pos, fig):
		fig.clear()
		ax = fig.add_axes([0, 0, 1, 1])
		# ax.axis('off')
		ax.set_facecolor('#FFF') # Background color

		# Lang color
		# langs = list({videos[node].channel.lang for node in graph.nodes if node in videos})
		# if '??' in langs:
		# 	langs.remove('??')
		# nblangs = len(langs)
		# langscolor = {langs[i]: colorsys.hsv_to_rgb(i/nblangs, .9, .9) for i in range(nblangs)}
		# langscolor['??'] = '#888'
		langscolor = {'??': '#888', 'fr': '#88F', 'en': '#F88'}

		nx.draw_networkx_nodes(subgraph,pos,
			node_size=[subgraph.degree[node]*10 for node in subgraph.nodes],
			node_color=[langscolor[videos[node].channel.lang if node in videos else '??'] for node in subgraph.nodes],
		)

		# Other's edges
		edges_to_draw = [e for e in subgraph.edges.data() if e[2]['cmps'] > 0 and not e[2]['cmp_by_me']]
		nx.draw_networkx_edges(subgraph,pos,
			edgelist=edges_to_draw,
			width=[2*math.sqrt(e[2]['cmps']) for e in edges_to_draw],
			edge_color='#779',
		)

		# My edges
		edges_to_draw = [e for e in subgraph.edges.data() if e[2]['cmp_by_me']]
		nx.draw_networkx_edges(subgraph,pos,
			edgelist=edges_to_draw,
			width=0.5,
			edge_color="#000",
		)

		# Recommended new edges
		edges_to_draw = []
		recom_nodes = set()
		for e in subgraph.edges.data():
			if e[2]['cmps'] == 0:
				edges_to_draw.append(e)
				recom_nodes.add(e[0])
				recom_nodes.add(e[1])

		nx.draw_networkx_edges(subgraph,pos,
			edgelist=edges_to_draw,
			width=1,
			edge_color="#080",
			style='dashed',
		)

		# Labels
		nx.draw_networkx_labels(subgraph,pos,
			font_size=8,
			font_color="#0008",
			labels={node: f"{videos[node].channel.name}\n{videos[node].title}" if node in recom_nodes else '' for node in subgraph.nodes}
		)

		# print(f"Saving {filename}...")

		warnings.filterwarnings("ignore", category=UserWarning)
		plt.savefig(filename)

	fig = _prepare_image()
	# pos = nx.circular_layout(subgraph)
	pos = nx.random_layout(subgraph, seed=94)
	# pos = nx.spectral_layout(subgraph, weight='cmps')

	# t = time.time()
	# pos = nx.fruchterman_reingold_layout(subgraph, pos = pos, weight='cmps')
	# _do_graph(pos)
	# print(f"Fruchterman Reingold in: {time.time() - t:0.3f}s")

	# t = time.time()
	# pos = radialized_layout(subgraph, full_graph=graph, pos=pos, weight='cmps')
	# print(f"Radialized in: {time.time() - t:0.3f}s")
	# _do_graph(pos, fig)

	gen = ForceLayout(subgraph, pos=pos, weight=_inv_weights)
	max_duration = 150 # seconds
	i = 0
	min_move=0.002
	tension_min = np.inf
	for frame in range(int(max_duration)):
		refresh = time.time()
		move = 0
		tension = 0
		while time.time() < refresh + 1:
			m = gen.iterate(power=0.001, repulse_upper_bound=2, inertia_factor=0.8)
			move = max(move, m[0])
			tension = max(tension, m[1])
			i += 1

		if tension < tension_min:
			_do_graph(gen.get_pos(), fig)
			tension_min = tension
		print(f"{i} iterations ({i/(frame+1):0.2f}ips) - m={move:0.3f} ({move/min_move:0.1f}x) tension={tension:0.5f}{'*' if tension == tension_min else ''}")
		if move < min_move:
			break

	# Ends plt
	plt.close()
