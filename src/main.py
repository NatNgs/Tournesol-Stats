import sys

import scripts.basic_grapher2 as grph
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
	grph.draw_graph_to_file(graph, videos, f"data/output/graph_{target_user}_{date}.png")


