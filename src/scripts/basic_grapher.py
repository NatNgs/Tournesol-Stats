import colorsys
import math
import matplotlib.pyplot as plt
import networkx as nx

from model.channel import Channel
from model.comparisons import ComparisonFile, ComparisonLine
from model.video import Video

def get_graph(input_dir: str, target_user: str, videos: dict[str,Video]):
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

	print('Graphing...')
	do_graph(graph, target_user, videos)

	print('Computing disconnectivity...')
	avgdists = compute_avgdists(graph)
	graph_disconnectivity = compute_disconnectivity(avgdists)
	print(f"Graph disconectivity: {graph_disconnectivity:0.4f}")

	print('End.')

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

def compute_avgdists(graph: nx.Graph):
	for edge in graph.edges.data():
		edge[2]['weight'] = 1/edge[2]['cmps']

	lengths = dict(nx.all_pairs_dijkstra_path_length(graph))
	return [sum(lengths[node].values())/len(lengths[node]) for node in graph.nodes]

def compute_disconnectivity(avgdists:list[float]):
	#return max(avgdists) # max
	#return sum(avgdists)/len(avgdists) # avg
	return sum([x*x for x in avgdists])/len(avgdists) # sqavg (long distance makes higher change)

def do_graph(graph: nx.Graph, user: str, videos: dict[str, Video]):
	pos = nx.spring_layout(graph, pos=nx.circular_layout(graph))

	# Prepare graph
	plt.box(False)
	plt.clf()
	plt.tight_layout()
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

	# Labeld
	nx.draw_networkx_labels(graph,pos,
		font_size=8,
		font_color="#0008",
		labels={node: f"{videos[node].channel.name}\n{videos[node].title}" if node in videos and graph.degree[node] <= 4 else '' for node in graph.nodes}
	)

	plt.savefig(f"data/output/graph_{user}_basic.png")
