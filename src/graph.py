import random
import sys
import networkx as nx
import numpy as np

import scripts.grapher as grph
import scripts.data_fetcher as fetcher

if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) <= 2:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir> <user>
	dataDir:
		Directory where the public dataset is located
		(ex: /data/input/tournesol_dataset_2023mmdd)
	user:
	 	User to get the statistics from
		(ex: NatNgs)
""")
		exit(-1)

	input_dir = sys.argv[1]
	target_user = sys.argv[2]

	# Init data
	videos = fetcher.fetch_by_user(input_dir, target_user) # {vid: Video, ...}

	# Build Graph
	graph = grph.build_graph(input_dir, target_user)

	# Do find most distant nodes
	grph.add_recommended_nodes(graph, videos)

	# Print graph picture
	date = input_dir.split('_')[-1][:8]

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
	pos = grph.optimize_graph_pos(subgraph, pos, 600)
	grph.draw_graph_to_file(subgraph, pos, videos, f"data/output/graph_{target_user}_{date}.svg")
