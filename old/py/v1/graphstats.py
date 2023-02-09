import math
import matplotlib.pyplot as plt
import networkx as nx

### Common variables
G = nx.Graph()

### PARSING selft data
datafolder = 'tournesol_export_20230205T150252Z'
FILTER_USER = 'NatNgs'

def unload_comparison_data(graph, datafolder, criteria):
	# public_username,video_a,video_b,criteria,weight,score
	cmpFile = open(datafolder + '/comparisons.csv', 'r', encoding='utf-8')

	# Skip first line (headers)
	cmpFile.readline()

	while True:
		line = cmpFile.readline()

		# if line is empty, end of file is reached
		if not line:
			break

		ldata = line.split(',')
		if ldata[0] == FILTER_USER and ldata[3] == criteria:
			nd1 = ldata[1]
			nd2 = ldata[2]
			graph.add_edge(nd1 if nd1 < nd2 else nd2, nd2 if nd1 < nd2 else nd1, cmps=1, cmp_by_me=True)

# Parsing comparison data
unload_comparison_data(G, datafolder, 'largely_recommended')

print('nodes:', len(G.nodes))
print('edges:', len(G.edges))


def unload_others_comparison_data(graph, datafolder, criteria):
	# public_username,video_a,video_b,criteria,weight,score
	cmpFile = open(datafolder + '/comparisons.csv', 'r', encoding='utf-8')

	# Skip first line (headers)
	cmpFile.readline()

	nodes = set(graph.nodes)

	while True:
		line = cmpFile.readline()

		# if line is empty, end of file is reached
		if not line:
			break

		ldata = line.split(',')
		usr = ldata[0]
		nd1 = ldata[1]
		nd2 = ldata[2]
		ctr = ldata[3]
		if usr != FILTER_USER and ctr == criteria and nd1 in nodes and nd2 in nodes:
			edge = G.get_edge_data(nd1 if nd1 < nd2 else nd2, nd2 if nd1 < nd2 else nd1, None)
			if edge:
				edge['cmps'] = edge['cmps']+1
			else:
				graph.add_edge(nd1 if nd1 < nd2 else nd2, nd2 if nd1 < nd2 else nd1, cmps=1)

# Parsing comparison data
unload_others_comparison_data(G, datafolder, 'largely_recommended')

print('edges (+others):', len(G.edges))

# Computing weights
def compute_avgdists(graph):
	for edge in graph.edges.data():
		edge[2]['weight'] = 1/edge[2]['cmps']

	lengths = dict(nx.all_pairs_dijkstra_path_length(graph))
	return [sum(lengths[node].values())/len(lengths[node]) for node in graph.nodes]

def compute_avg_avgdist(avgdists):
	#return max(avgdists) # max
	#return sum(avgdists)/len(avgdists) # avg
	return sum([x*x for x in avgdists])/len(avgdists) # sqavg

avgdists = compute_avgdists(G)
avg_avgdist = compute_avg_avgdist(avgdists)
print(f"Average-sqavg-dist: {avg_avgdist:0.4f}")

def simulate_edge(graph, node1, node2):
	# Add new edge
	graph.add_edge(node1, node2, cmps=1)
	# Simulate
	sim = compute_avg_avgdist(compute_avgdists(graph))
	# Remove edge
	graph.remove_edge(node1, node2)
	return {'nd1': node1, 'nd2': node2, 'avg': sim}

def simulate_missing_edges(graph, avgdists):
	simulated = []
	print('Simulating new edges...')

	for node1 in graph.nodes:
		for node2 in graph.nodes:
			if node1 < node2 and not G.get_edge_data(node1, node2, None):
				simulated.append(simulate_edge(graph, node1, node2))

	return simulated

recommended_edges = simulate_missing_edges(G, avgdists)
excluded_from_recom = set()

# Add recommended edges to graph
recommended_edges.sort(key=lambda x: (G.degree[x['nd1']] + G.degree[x['nd2']], -x['avg']))
while recommended_edges:
	recom = recommended_edges.pop(0)
	node1 = recom['nd1']
	node2 = recom['nd2']
	if not (node1 in excluded_from_recom) and not (node2 in excluded_from_recom):
		diff=avg_avgdist - recom['avg']
		if diff == 0:
			continue
		G.add_edge(node1, node2, cmps=0, weight=diff, recom=diff)
		excluded_from_recom.add(node1)
		excluded_from_recom.add(node2)

##
##
## GRAPHING
##
##

def do_graph(graph):
	pos = nx.spring_layout(graph, pos=nx.circular_layout(graph))
	plt.box(False)
	plt.clf()
	plt.tight_layout()
	fig = plt.figure(figsize=(10, 5), frameon=False)
	ax = fig.add_axes([0, 0, 1, 1])
	ax.axis('off')

	nx.draw_networkx_nodes(graph, pos, node_size=[75 for node in graph.nodes])

	# Other's edges
	edges_to_draw = [e for e in graph.edges.data() if e[2]['cmps'] > 1]
	nx.draw_networkx_edges(graph,pos,
		edgelist=edges_to_draw,
		width=[2*math.sqrt(e[2]['cmps']) for e in edges_to_draw],
		edge_color='#888',
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
		edge_color="#FF0",
		alpha=[e[2]['recom']/max_recom for e in edges_to_draw],
		style='dashed'
	)
	edges_to_draw.sort(key=lambda x: x[2]['recom'], reverse=True)
	for edge in edges_to_draw[:5]:
		print(edge[0], edge[1], f"{(100*edge[2]['recom']):0.2f}%")

	nx.draw_networkx_labels(graph, pos, font_size=8, font_color="#0008")
	plt.savefig("graph_All.png")

do_graph(G)
