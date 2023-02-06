import sys

from scripts.data_fetcher import do_fetch_data

if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) < 2:
		raise 'Missing arguments: 1-Data directory (ex: /data/input/tournesol_export_2023mmddThhmmssZ), 2-User (ex: NatNgs)'
	input_dir = sys.argv[1]
	target_user = sys.argv[2]

	# Init lang
	data = do_fetch_data(input_dir, target_user) # {'channels': {cid: Channel, ...}, 'videos': {vid: Video, ...}}
