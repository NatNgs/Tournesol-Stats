import math
import time
import matplotlib.pyplot as plt
import networkx as nx

from model.channel import Channel
from model.comparisons import ComparisonFile, ComparisonLine
from model.video import Video

def get_graph(input_dir: str, target_user: str, channels: dict[str,Channel], videos: dict[str,Video]):
	graph = nx.Graph()
	comparisons = ComparisonFile(input_dir)

	# Parsing comparison data
	comparisons.foreach(lambda linedata: unload_self_comparison_data(graph, linedata, target_user, 'largely_recommended'))
	print('nodes:', len(graph.nodes))
	self_edges_cnt = len(graph.edges)
	print('edges (myself):', self_edges_cnt)

	# Parsing comparison data
	self_nodes: set[str] = set(graph.nodes)
	comparisons.foreach(lambda linedata: unload_others_comparison_data(graph, linedata, target_user, 'largely_recommended', self_nodes))
	print('edges (others):', len(graph.edges)-self_edges_cnt)

	avgdists = compute_avgdists(graph)
	graph_disconnectivity = compute_disconnectivity(avgdists)
	print(f"Graph disconectivity: {graph_disconnectivity:0.4f}")

	print('Simulating new edges...')
	recommended_edges = simulate_missing_edges(graph, graph_disconnectivity)
	add_recommended_edges(graph, recommended_edges, graph_disconnectivity)

	print('Graphing...')
	do_graph(graph, videos)
	print('End.')

def unload_self_comparison_data(graph: nx.Graph, ldata: ComparisonLine, filter_user: str, criteria: str):
	if ldata.user == filter_user and ldata.criteria == criteria:
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


def simulate_edge(graph: nx.Graph, node1: str, node2: str):
	# Add new edge
	graph.add_edge(node1, node2, cmps=1)
	# Simulate
	disc = compute_disconnectivity(compute_avgdists(graph))
	# Remove edge
	graph.remove_edge(node1, node2)
	return {'nd1': node1, 'nd2': node2, 'disc': disc}

def simulate_missing_edges(graph: nx.Graph, disconnectivity: float):
	simulated = []

	# Ignoring nodes with highest degree
	simulating_nodes = list(graph.nodes)
	simulating_nodes.sort(key=lambda node: graph.degree[node])
	simulating_nodes = simulating_nodes[:5]

	# Computing every missing edge between non-highest-degree nodes
	begin = time.perf_counter()
	t = begin
	cnt = 0
	for node1 in simulating_nodes:
		for node2 in simulating_nodes:
			if node1 < node2 and not graph.get_edge_data(node1, node2, None):
				cnt = cnt + 1
				new_edge_data = simulate_edge(graph, node1, node2)
				if new_edge_data['disc'] < disconnectivity:
					simulated.append(new_edge_data)

				t2 = time.perf_counter()
				if t2 > t+5:
					print(f"Simulating... ({cnt}/{int(len(simulating_nodes)*(len(simulating_nodes)-1)/2)} simulated & {len(simulated)} kept in {int(t2-begin)}s)")
					t = t2

	return simulated


def add_recommended_edges(graph: nx.Graph, recommended_edges: list, disconnectivity: float):
	recommended_edges.sort(key=lambda x: (graph.degree[x['nd1']] + graph.degree[x['nd2']], -x['disc']))
	recommended_edges = recommended_edges[:10]
	while recommended_edges:
		recom = recommended_edges.pop(0)
		node1 = recom['nd1']
		node2 = recom['nd2']
		diff=disconnectivity - recom['disc']
		graph.add_edge(node1, node2, cmps=0, weight=diff, recom=diff)

def do_graph(graph: nx.Graph, videos: dict[str, Video]):
	pos = nx.spring_layout(graph, pos=nx.circular_layout(graph))

	# Prepare graph
	plt.box(False)
	plt.clf()
	plt.tight_layout()
	fig = plt.figure(figsize=(10, 5), frameon=False)
	ax = fig.add_axes([0, 0, 1, 1])
	# ax.axis('off')
	ax.set_facecolor('#aaa') # Background color

	# Lang color
	langscolor = {
		'fr': '#22A',
		'en': '#A33',
		'es': '#AA3',
		'ja': '#FFF',
		'ko': '#A83',
		'ar': '#333',
		'de': '#883',
		'??': '#888'
	}
	nx.draw_networkx_nodes(graph,pos,
		node_size=[graph.degree[node]*10 for node in graph.nodes],
		node_color=[langscolor[videos[node].channel.lang] for node in graph.nodes],
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

	# Recommended edges
	edges_to_draw = [e for e in graph.edges.data() if e[2]['cmps'] == 0]
	max_recom=max([e[2]['recom'] for e in edges_to_draw])
	print('Recommending', len(edges_to_draw), 'comparisons')
	nx.draw_networkx_edges(graph,pos,
		edgelist=edges_to_draw,
		width=[(0.5+ e[2]['recom']/max_recom) for e in edges_to_draw],
		edge_color="#080",
		alpha=[e[2]['recom']/max_recom for e in edges_to_draw],
		style='dashed'
	)
	edges_to_draw.sort(key=lambda x: x[2]['recom'], reverse=True)
	for edge in edges_to_draw[:5]:
		print(edge[0], edge[1], f"{(100*edge[2]['recom']):0.2f}%")

	nx.draw_networkx_labels(graph,pos,
		font_size=8,
		font_color="#0008",
		labels={node: videos[node].channel.name for node in graph.nodes}
	)
	plt.savefig("data/output/graph_All.png")
