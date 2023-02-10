import colorsys
import math
import matplotlib.pyplot as plt
import networkx as nx

from model.comparisons import ComparisonFile, ComparisonLine
from model.video import Video

def build_graph(input_dir: str, target_user: str, videos: dict[str,Video]):
	graph = nx.Graph()
	comparisons = ComparisonFile(input_dir)

	# Parsing comparison data
	comparisons.foreach(lambda linedata: unload_self_comparison_data(graph, linedata, target_user, 'largely_recommended', videos))
	print('nodes:', len(graph.nodes))
	self_edges_cnt = len(graph.edges)
	print('edges (myself):', self_edges_cnt)

	# Parsing comparison data
	self_nodes: set[str] = set(graph.nodes)
	comparisons.foreach(lambda linedata: unload_others_comparison_data(graph, linedata, target_user, 'largely_recommended', self_nodes))
	print('edges (others):', len(graph.edges)-self_edges_cnt)

	return graph

def unload_self_comparison_data(graph: nx.Graph, ldata: ComparisonLine, filter_user: str, criteria: str, videos: dict[str, Video]):
	if ldata.user == filter_user and ldata.criteria == criteria and ldata.vid1 in videos and ldata.vid2 in videos:
		graph.add_edge(ldata.vid1, ldata.vid2, cmps=1, cmp_by_me=True)

def unload_others_comparison_data(graph: nx.Graph, ldata: ComparisonLine, filter_user: str, criteria, nodes: set[str]):
	if ldata.user != filter_user and ldata.criteria == criteria and ldata.vid1 in nodes and ldata.vid2 in nodes:
		if graph.has_edge(ldata.vid1, ldata.vid2):
			edge = graph.get_edge_data(ldata.vid1, ldata.vid2, None)
			edge['cmps'] = edge['cmps']+1
		else:
			graph.add_edge(ldata.vid1, ldata.vid2, cmps=1)

def draw_graph_to_file(graph: nx.Graph, videos: dict[str, Video], recommendations: list[(str, str)], filename: str):
	# Add recommended edges
	graph.add_edges_from(recommendations, weight=0.5, cmps=0)

	pos = nx.spring_layout(graph, pos=nx.circular_layout(graph), weight='weight')

	# Prepare graph
	plt.box(False)
	plt.clf()
	plt.tight_layout()
	plt.rc('axes', unicode_minus=False)
	fig = plt.figure(figsize=(20, 10), frameon=False)
	ax = fig.add_axes([0, 0, 1, 1])
	# ax.axis('off')
	ax.set_facecolor('#aaa') # Background color

	# Lang color
	langs = list({videos[node].channel.lang for node in graph.nodes if node in videos})
	if '??' in langs:
		langs.remove('??')
	nblangs = len(langs)
	langscolor = {langs[i]: colorsys.hsv_to_rgb(i/nblangs, .9, .9) for i in range(nblangs)}
	langscolor['??'] = '#888'

	nx.draw_networkx_nodes(graph,pos,
		node_size=[graph.degree[node]*10 for node in graph.nodes],
		node_color=[langscolor[videos[node].channel.lang if node in videos else '??'] for node in graph.nodes],
	)

	# Other's edges
	edges_to_draw = [e for e in graph.edges.data() if e[2]['cmps'] > 1]
	nx.draw_networkx_edges(graph,pos,
		edgelist=edges_to_draw,
		width=[2*math.sqrt(e[2]['cmps']) for e in edges_to_draw],
		edge_color='#779',
	)

	# My edges
	edges_to_draw = [e for e in graph.edges.data() if 'cmp_by_me' in e[2]]
	nx.draw_networkx_edges(graph,pos,
		edgelist=edges_to_draw,
		width=1,
		edge_color="#000",
	)

	# Recommended new edges
	edges_to_draw = [e for e in graph.edges.data() if e[2]['cmps'] == 0]
	nx.draw_networkx_edges(graph,pos,
		edgelist=edges_to_draw,
		width=1,
		edge_color="#080",
		style='dashed'
	)

	# Labels
	nx.draw_networkx_labels(graph,pos,
		font_size=8,
		font_color="#0008",
		labels={node: f"{videos[node].channel.name}\n{videos[node].title}" if node in videos and graph.degree[node] <= 4 else '' for node in graph.nodes}
	)

	plt.savefig(filename)

def print_furthest_nodes(graph: nx.Graph, videos: dict[str, Video]):
	# Exclude from search nodes with too many connexions (most of the time will not be in furthest, and reduces a lot time to compute)
	nodes_degree = [(node, graph.degree(node, None)) for node in graph.nodes]
	aggregated = list()
	for pair in nodes_degree:
		while len(aggregated) < pair[1]:
			aggregated.append(0)
		aggregated[pair[1]-1] = aggregated[pair[1]-1] + 1

	print('Node count by degree:', aggregated)

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
		shrt_paths = nx.shortest_path_length(graph, source=node1, weight=None) # {target: shortestpath}
		max_min = max(shrt_paths.values())
		if max_min > max_max_min:
			paths = []
			max_max_min = max_min

		if max_min == max_max_min:
			for node2 in shrt_paths:
				if node2 > node1 and shrt_paths[node2] == max_min:
					paths.append((node1, node2))

	print('Maximum distance =', max_max_min)
	# Sort by 1: max degree, 2: sum of degrees
	paths.sort(key=lambda pair: (
		max(graph.degree(pair[0]), graph.degree(pair[1])),
		graph.degree(pair[0]) + graph.degree(pair[1])
	))

	print('\nRecommending:')
	already_relinked = set()
	recommending = []
	for path in paths:
		if not (path[0] in already_relinked or path[1] in already_relinked):
			print(f"{videos[path[0]]}\n{videos[path[1]]}\n")
			already_relinked.add(path[0])
			already_relinked.add(path[1])
			recommending.append(path)
	return recommending
