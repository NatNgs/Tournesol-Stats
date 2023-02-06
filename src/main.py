import sys

from scripts.data_fetcher import do_fetch_data

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
		(ex: NatNgs)""")
		exit(-1)

	input_dir = sys.argv[1]
	target_user = sys.argv[2]

	# Init lang
	data = do_fetch_data(input_dir, target_user) # {'channels': {cid: Channel, ...}, 'videos': {vid: Video, ...}}
