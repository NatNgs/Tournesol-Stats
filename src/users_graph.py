import logging
import math
import matplotlib.pyplot as plt
import networkx as nx
import argparse
import colorsys
import time
import warnings
from model.comparisons import ComparisonFile, ComparisonLine
import numpy as np
from scripts import svg

# Filter users
USER_MIN_VIDEOS = 5

## Graph nodes localization optimization
TOP_EDGES = 10 # Max number of edges to keep per node
MAX_SPRING_DURATION = 150 # seconds
MAX_SPRING_ITERATIONS = 1e5

def load_graph(datasetpath: str, limit: str):
	graph = nx.Graph()
	cf = ComparisonFile(datasetpath)
	data: dict[str,set[str]] = dict() # user: {vid1, vid2, ...}
	users_date: dict[str,str] = dict() # user: first_comparison_date

	def parser(line: ComparisonLine):
		if line.criteria != 'largely_recommended' or limit and line.date < limit:
			return

		if not line.user in data:
			data[line.user] = set()
			users_date[line.user] = line.date
		elif users_date[line.user] > line.date:
			users_date[line.user] = line.date

		data[line.user].add(line.vid1)
		data[line.user].add(line.vid2)
	cf.foreach(parser)

	users = [u for u,d in data.items() if len(d) > USER_MIN_VIDEOS]
	users = sorted(users, key=lambda u: len(data[u]), reverse=True)

	edges:dict[str,list[tuple[int,str,float,float]]] = dict()
	for i,u1 in enumerate(users[1:], start=1):
		for u2 in users[:i]:
			num = len(data[u1].intersection(data[u2]))
			if num > 0:
				pct = float(num)/(len(data[u1]) + len(data[u2]) - num)
				maxpct = float(num)/min(len(data[u1]), len(data[u2]))
				edges.setdefault(u1, list()).append((num,u2,pct,maxpct))
				edges.setdefault(u2, list()).append((num,u1,pct,maxpct))

	for u,lst in edges.items():
		lst.sort(reverse=True)
		for e in lst[:TOP_EDGES]:
			graph.add_edge(u, e[1], num=e[0], pct=e[2], maxpct=e[3])

		graph.nodes[u]['date'] = users_date[u]
		graph.nodes[u]['size'] = len(data[u])

	return graph



def get_graph_layout(graph: nx.Graph):
	print('Preparing graph layout', end='', flush=True)
	start = time.time()

	pos=nx.circular_layout(graph, center=(0,0))

	i:int =1
	itt:int =0
	while time.time() - start < MAX_SPRING_DURATION:
		print(f'.', end='', flush=True)
		# weight= pct / num
		pos = nx.spring_layout(graph, pos=pos, weight='num', iterations=i, scale=None)
		itt += i

		if itt > MAX_SPRING_ITERATIONS:
			break

		# Estimate number of iterations so that next loop takes around 10% of the process
		i = int(MAX_SPRING_DURATION/10 * itt / (time.time() - start))+1

	end = time.time()
	print(f"\nOptimized nodes location with {itt} spring iterations in {end-start:0.3f}s")

	return pos




def float_to_color(weight: float, min_c:float, mm_c:float) -> tuple[float,float,float]:
	return colorsys.hsv_to_rgb((weight-min_c)/mm_c * (240/360), .9, .9)



def graph_to_svg(graph: nx.Graph, filename: str):
	nodes = list(graph.nodes)
	pos = get_graph_layout(graph)

	##
	## Prepare image
	##
	print('\nPreparing image...')
	start = time.time()
	plt.box(False)
	plt.clf()
	plt.tight_layout()
	plt.rcParams['svg.fonttype'] = 'none'
	plt.rc('axes', unicode_minus=False)

	# Output svg dimensions
	size = 4 * (graph.number_of_nodes()+1)**0.25
	print(f"Image size: {size*1.4+1:.1f}x{size+1:.1f}")
	fig = plt.figure(figsize=(size*1.4+1, size+1), frameon=False)

	# Axis
	fig.clear()
	ax = fig.add_axes([0, 0, 1, 1])
	ax.axis('off')
	# ax.axhline(y=0)
	# ax.axvline(x=0)
	ax.set_facecolor('#FFF') # Background color

	##
	## Printing
	##

	# Nodes Colors
	dates = {d:i for i,d in enumerate(sorted(graph.nodes[n]['date'] for n in nodes))}
	max_date = max(dates.values())
	nodes_colors = {n: float_to_color(dates[graph.nodes[n]['date']], 0, max_date) for n in nodes}
	node_size=[math.sqrt(graph.nodes[n]['size']) for n in nodes],

	## Edges
	edges = [
		(u1,u2) for (u1, u2, d) in graph.edges.data()
		if d['pct'] > 0.01 # Ignore if edge alpha (opacity) <1%
	]
	print(f"Printing {len(edges)}/{graph.number_of_edges()} edges ({len(edges)/graph.number_of_edges():.0%})")

	nx.draw_networkx_edges(graph,
		pos=pos,
		edgelist=edges,
		# Average color of both nodes
		edge_color=[(np.array(nodes_colors[e[0]]) + np.array(nodes_colors[e[1]]))/2 for e in edges],
		# opacity=edge's pct value
		alpha=[graph[e[0]][e[1]]['pct'] for e in edges],
		# Width proportional to number of shared compared videos (sqrt because node sizes are sqrtd)
		width=[math.sqrt(graph[u1][u2]['num'])/5 for (u1,u2) in edges],
	)

	# Nodes
	nx.draw_networkx_nodes(graph,
		pos=pos,
		nodelist=nodes,
		node_size=node_size,
		node_color=[nodes_colors[n] for n in nodes],
	)

	# Labels
	nx.draw_networkx_labels(graph,
		pos=pos,
		font_size=2,
		font_family='mono',
		font_color='#888',
	)

	end = time.time()
	print(f"Image preparred in {end-start:0.2f}s")

	##
	## Saving to file
	##
	print(f"Saving graph to {filename}...", end='', flush=True)
	start = time.time()

	logging.getLogger('matplotlib.font_manager').disabled = True
	warnings.filterwarnings("ignore", category=Warning)
	plt.savefig(filename, format='svg')
	end = time.time()
	print(f"({end-start:0.2f}s)")

	# End plt
	plt.close()



##############
##   MAIN   ##
##############

if __name__ == '__main__':

	# Unload parameters
	parser = argparse.ArgumentParser()
	parser.add_argument('out', help='Name of the SVG file to be generated with the graph image', type=str)
	parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located (default: %(default))', default='data/tournesol_dataset', type=str)
	parser.add_argument('-l', '--limit', help='If set, will only fetch data after the given date (ISO format like 2000-12-31)', type=str, default='')

	args = vars(parser.parse_args())

	try:
		# Loading data
		print('Loading comparisons and generating graph...')
		start = time.time()
		graph:nx.Graph = load_graph(args['tournesoldataset'], args['limit'])
		end = time.time()
		print('Loaded', graph, f"in {end - start:0.3f}s")

		# Reducing data (removing disconnected nodes)
		largest_group = max(nx.connected_components(graph), key=len)
		graph.remove_nodes_from(n for n in list(graph.nodes) if not n in largest_group)
		print('Largest connected subgraph:', graph)
		print()

		# Graphing
		graph_to_svg(graph, args['out'])
		svg.optimize(args['out'])
	except KeyboardInterrupt:
		print('\n\t\t-   KILLED   -\n')
		pass
