import random
import sys
import networkx as nx
from model.youtube_api import YTData

import scripts.grapher as grph


if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) <= 3:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <tournesolDataset> <cache> <user>
	tournesolDataset:
		Directory where the public dataset is located
		(ex: data/tournesol_dataset)
	cache:
		Cached YT video information file
		(ex: data/YTData_cache.json)
	user:
	 	User to get the statistics from
		(ex: NatNgs)
""")
		exit(-1)

	tournesol_dataset = sys.argv[1]
	ytdata_cache = sys.argv[2]
	target_user = sys.argv[3]

	# Init data
	ytdata = YTData()
	ytdata.load(ytdata_cache)

	# Build Graph
	graph = grph.build_graph(tournesol_dataset, target_user)
	ytdata.update(vids=[node for (node, byme) in graph.nodes(data='cmp_by_me') if byme], save=ytdata_cache)

	# Do find most distant nodes
	grph.add_recommended_nodes(graph, ytdata.videos)

	# Sort nodes by degree
	nodes_order = grph.get_ordered_nodes(graph)

	pos = {}
	for nb in range(1, len(nodes_order)):
		pos[nodes_order[nb-1]] = [random.random(), random.random()]
		# subgraph = nx.subgraph_view(graph, filter_node=lambda node: node in pos)
		# print(f"\t### {nb}/{len(nodes_order)} nodes ###")
		# pos = grph.optimize_graph_pos(subgraph, pos, nb)
		# grph.draw_graph_to_file(subgraph, pos, videos, f"data/output/graph_{target_user}_{date}.svg")

	subgraph = nx.subgraph_view(graph, filter_node=lambda node: node in pos)
	pos = grph.optimize_graph_pos(subgraph, pos, 300)
	grph.draw_graph_to_file(subgraph, pos, ytdata.videos, f"data/output/graph_{target_user}.svg")
