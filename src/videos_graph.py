import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import argparse
import colorsys
import time
import warnings
from model.collectivecriteriascores import CollectiveCriteriaScoresFile
from model.comparisons import ComparisonFile, ComparisonLine
from scripts import svg
from scripts.nxlayouts import radialized_layout


def load_graph(datasetpath: str, limit: str, user: str):
	graph = nx.Graph()
	cf = ComparisonFile(datasetpath)
	nodes_size: dict[str,int] = dict()

	def parser(line: ComparisonLine):
		if limit and line.date < limit:
			return
		if line.criteria == 'largely_recommended':
			nodes_size[line.vid1] = nodes_size.get(line.vid1,0) + 1
			nodes_size[line.vid2] = nodes_size.get(line.vid2,0) + 1

		if user and line.user != user:
			return
		if not graph.has_edge(line.vid1, line.vid2):
			graph.add_edge(line.vid1, line.vid2, spring=1)
		else:
			graph[line.vid1][line.vid2]['spring'] += 1

	cf.foreach(parser)

	for n in graph.nodes:
		graph.nodes[n]['weight'] = nodes_size.get(n, 1)

	return graph

def weight_to_color(weight, min_c:float, mm_c:float):
	return colorsys.hsv_to_rgb((weight-min_c)/mm_c * (128/360), .9, .9)

def get_graph_layout(graph: nx.Graph):
	print('Preparing graph layout', end='', flush=True)
	start = time.time()
	pos = radialized_layout(graph, pos=nx.circular_layout(graph))

	i=1 if graph.number_of_nodes() > 500 else 500 - graph.number_of_nodes()
	i *= 10

	itt=0
	while time.time() - start < 300:
		print('.', end='', flush=True)
		pos = nx.spring_layout(graph, pos=pos, weight='spring', iterations=i)
		itt += i
		i += 1

	end = time.time()
	print()
	print(f"{itt} spring iterations in {end-start:0.3f}s")

	return pos

def graph_to_svg(unorderedgraph: nx.Graph, colors: dict[str, float], filename: str):
	# Compute node location
	pos = get_graph_layout(unorderedgraph)

	# Subgraph to show (remove helper edges, order nodes by color)
	nodes = sorted(unorderedgraph.nodes, key=colors.get)
	graph = nx.Graph()
	graph.add_nodes_from(nodes)
	graph.add_edges_from(e for e in unorderedgraph.edges.data() if e[2]['spring'] >= 1)


	print('Preparing image...', graph)
	# node color
	min_c = min(colors.values())
	mm_c = max(colors.values()) - min_c
	print('min & max colors:', min_c, min_c + mm_c)
	colors = [weight_to_color(colors[n], min_c, mm_c) for n in nodes]

	# Prepare image
	plt.box(False)
	plt.clf()
	plt.tight_layout()
	plt.rcParams['svg.fonttype'] = 'none'
	plt.rc('axes', unicode_minus=False)

	# Output svg dimensions
	size = (graph.number_of_nodes()+1)**0.25
	print(f"Image size: {size*1.4+1:.1f}x{size+1:.1f}")
	fig = plt.figure(figsize=(size*1.4+1, size+1), frameon=False)

	# Axis
	fig.clear()
	ax = fig.add_axes([0, 0, 1, 1])
	ax.axis('off')
	ax.set_facecolor('#FFF') # Background color

	nodes_width = dict(unorderedgraph.nodes(data="weight"))
	min_w = min(nodes_width.values())
	mm_w = max(nodes_width.values()) - min_w
	min_display = 1
	mm_display = 25 - min_display
	nx.draw_networkx_nodes(graph,
		pos=pos,
		nodelist=nodes,
		node_size=[min_display+mm_display*(nodes_width[n]-min_w)/mm_w for n in nodes],
		node_color=colors
	)

	nx.draw_networkx_edges(graph,
		pos=pos,
		edge_color='#0004',
		width=0.1,
	)

	print(f"Saving graph to {filename}...")

	warnings.filterwarnings("ignore", category=UserWarning)
	plt.savefig(filename)

	# End plt
	plt.close()


def compute_colors(graph: nx.Graph, mode: str, tournesoldataset: str) -> dict[str, float]:
	colors: dict[str, float] = None
	start: float = None

	start = time.time()
	if mode == 'score':
		print('Collective criteria scores...', flush=True)
		colors = CollectiveCriteriaScoresFile(tournesoldataset).get_vids_scores('largely_recommended', vids=graph.nodes)

	elif mode == 'degree':
		print('Degrees...', flush=True)
		colors = {n: len(graph[n]) for n in graph.nodes}

	elif mode == 'sqrtdeg':
		print('Square root of Degrees...', flush=True)
		colors = {n: len(graph[n])**0.5 for n in graph.nodes}

	elif mode == 'distmax':
		print('Distance to maximum degree node...', flush=True)
		degs = {n: len(graph[n]) for n in graph.nodes}
		max_deg_node = sorted(degs.keys(), key=degs.get, reverse=True)[0]
		colors = nx.shortest_path_length(graph, source=max_deg_node, weight=None)

	elif mode == 'closeness':
		## CLOSENESS
		print('Closeness centrality...', flush=True)
		edges = graph.size(weight=1)
		done = 0
		sub_start = start
		for e in graph.edges:
			colors = nx.incremental_closeness_centrality(graph, edge=e, prev_cc=colors)
			done += 1
			t = time.time()
			if t - sub_start > 5:
				print(f"({done}/{edges} - {done/edges:0.2%})")
				sub_start = t

	elif mode == 'katz-appx':
		## KATZ
		alpha=0.03
		print(f"Katz Centrality Approximated... alpha={alpha:0.3f}", flush=True)
		colors = nx.katz_centrality_numpy(graph, alpha)

	elif mode == 'katz':
		## KATZ
		print('Katz Centrality... alpha=', end='', flush=True)
		katz_alpha = 1/np.amax(np.abs(nx.adjacency_spectrum(graph)))
		end = time.time()
		print(katz_alpha, f"(computed alpha in: {end - start:0.3f}s)")

		start = time.time()
		colors = nx.katz_centrality_numpy(graph, katz_alpha)

	elif mode == 'rndwalk-appx':
		## RND WALK BETWEENNESS CENTRALITY
		print('Random walk betweenness centrality Approximated...', flush=True)
		colors = nx.approximate_current_flow_betweenness_centrality(graph, solver='lu', dtype=np.float32)

	elif mode == 'rndwalk':
		## RND WALK BETWEENNESS CENTRALITY
		print('Random walk betweenness centrality...', flush=True)
		colors = nx.current_flow_betweenness_centrality(graph, solver='lu', dtype=np.float32)

	else:
		raise f"Unknown mode '{mode}'"

	end = time.time()
	print(f"(colors computed in {end - start:0.3f}s)")

	print() ##
	return colors


##############
##   MAIN   ##
##############

if __name__ == '__main__':

	# Unload parameters
	parser = argparse.ArgumentParser()
	parser.add_argument('out', help='Name of the SVG file to be generated with the graph image', type=str)
	parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located (default: %(default))', default='data/tournesol_dataset', type=str)
	parser.add_argument('-l', '--limit', help='If set, will only fetch data after the given date (ISO format like 2000-12-31)', type=str, default='')
	parser.add_argument('-u', '--user', help='If set, will only fetch comparisons of this user', type=str, default='')
	parser.add_argument('-m', '--mode', type=str,
		help='Mode for computing weights for nodes color, default: %(default)',
		choices=[
			# @see function compute_weights
			'score',
			'degree', 'sqrtdeg',
			'distmax', 'closeness',
			'katz', 'katz-appx',
			'rndwalk', 'rndwalk-appx'
		],
		default='degree'
	)
	args = vars(parser.parse_args())

	# Extract videos id from comparisons
	# - Need to be compared by at least 3 different users
	graph:nx.Graph = load_graph(args['tournesoldataset'], args['limit'], args['user'])
	print('Loaded', graph)

	# def analyse_distances(graph: nx.Graph, ytdata: YTData):
	print('Largest connected subgraph: ', end='', flush=True)
	start = time.time()
	largest_group = max(nx.connected_components(graph), key=len)
	graph.remove_nodes_from(n for n in list(graph.nodes) if not n in largest_group)
	end = time.time()
	print(graph, f"(duration: {end - start:0.3f}s)")

	print() ##

	# Analyse distances
	weights: dict[str, float] = compute_colors(graph, args['mode'], args['tournesoldataset'])
	graph.remove_nodes_from(n for n in list(graph.nodes) if not n in weights)
	graph_to_svg(graph, weights, args['out'])
	svg.optimize(args['out'])
