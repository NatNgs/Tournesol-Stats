import argparse
import random
import networkx as nx
from dao.youtube_api import YTData

import scripts.grapher as grph


def graph(tournesol_dataset, YTDATA: YTData, target_user, ytdata_cache):
	# Build Graph
	graph = grph.build_graph(tournesol_dataset, target_user)
	YTDATA.update(vids=[node for (node, byme) in graph.nodes(data='cmp_by_me') if byme], save=ytdata_cache)

	# Do find most distant nodes
	grph.add_recommended_nodes(graph, YTDATA.videos)

	# Sort nodes by degree
	nodes_order = grph.get_ordered_nodes(graph)

	pos = {}
	for nb in range(1, len(nodes_order)):
		pos[nodes_order[nb-1]] = [random.random(), random.random()]
		# subgraph = nx.subgraph_view(graph, filter_node=lambda node: node in pos)
		# print(f"\t### {nb}/{len(nodes_order)} nodes ###")
		# pos = grph.optimize_graph_pos(subgraph, pos, nb)
		# grph.draw_graph_to_file(subgraph, pos, videos, f"output/graph_{target_user}_{date}.svg")

	subgraph = nx.subgraph_view(graph, filter_node=lambda node: node in pos)
	pos = grph.optimize_graph_pos(subgraph, pos, 300)
	grph.draw_graph_to_file(subgraph, pos, YTDATA.videos, f"output/graph_{target_user}.svg")



################
##### MAIN #####
################


# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json.gz', type=str)
parser.add_argument('-u', '--user', help='Get statistics for given user. If unset, will compute global statistics', type=str, default=None)
parser.add_argument('--fetch', help='If set, will fetch youtube API for updating data', action=argparse.BooleanOptionalAction, default=False)

args = vars(parser.parse_args())

YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

graph(args['tournesoldataset'], YTDATA, args['user'], args['cache'] if args['fetch'] else None)
