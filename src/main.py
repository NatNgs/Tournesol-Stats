import sys
import networkx as nx
import numpy as np

import scripts.grapher as grph
import scripts.data_fetcher as fetcher

if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) < 2:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir> <user>
	dataDir:
		Directory where the public dataset is located
		(ex: /data/input/tournesol_export_2023mmddThhmmssZ)
	user:
	 	User to get the statistics from
		(ex: NatNgs)
""")
		exit(-1)

	input_dir = sys.argv[1]
	target_user = sys.argv[2]

	# Init data
	videos = fetcher.do_fetch(input_dir, target_user) # {vid: Video, ...}

	# Build Graph
	graph = grph.build_graph(input_dir, target_user)

	# Do find most distant nodes
	grph.add_recommended_nodes(graph, videos)

	# Print graph picture
	date = input_dir.split('_')[-1][:8]

	# Sort nodes by degree
	nodes_order = grph.get_ordered_nodes(graph)

	pos = {
		nodes_order[0]: [0, 0]
	}
	for nb in range(2, len(nodes_order)):
		pos[nodes_order[nb-1]] = [(-1 if (nb % 2) < 1 else 1)/1024, (-1 if (nb % 4) < 2 else 1)/1024]
		subgraph = nx.subgraph_view(graph, filter_node=lambda node: node in pos)
		print('subgraph', subgraph)
		pos = grph.draw_graph_to_file(subgraph, pos, videos, f"data/output/graph_{target_user}_{date}.png")

