import sys

from scripts import basic_grapher, data_fetcher

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
	videos = data_fetcher.do_fetch(input_dir, target_user) # {vid: Video, ...}

	# Do statistics
	basic_grapher.get_graph(input_dir, target_user, videos)
