import argparse
import math
import random
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData
from scripts.elo import updateRating

def compute_elo_ranking(cmpFile:ComparisonFile, YTDATA: YTData, user: str):

	elo: dict[str,float] = dict() # vid: elo

	comps: list[tuple[str,str,float]] = list()
	def elo_update_line_parser(line: ComparisonLine):
		if line.criteria != 'largely_recommended' \
			or (user and user != line.user) \
			or (not line.vid1 in YTDATA.videos) or (not line.vid2 in YTDATA.videos) \
			or (not YTDATA.videos[line.vid1].get('title', '')) or (not YTDATA.videos[line.vid2].get('title', '')):
			return

		comps.append((line.vid1, line.vid2, line.score/-10.0))
		elo.setdefault(line.vid1, 1000.0)
		elo.setdefault(line.vid2, 1000.0)
	print('Extracting comparisons...')
	cmpFile.foreach(elo_update_line_parser)


	ELO_POWER: float = math.sqrt(1/len(elo))
	print('Running competition: ')
	for i in range(99):
		print(i+1, end=' ', flush=True)
		# Shuffle comps
		random.shuffle(comps)

		for c in comps:
			updatedElo = updateRating(elo[c[0]], elo[c[1]], c[2], ELO_POWER)
			elo[c[0]] = updatedElo[0]
			elo[c[1]] = updatedElo[1]
	print('\n')
	sortedKeys = sorted(elo.keys(), key=elo.get, reverse=True)

	# Show top
	for vid in sortedKeys[:10]:
		print(f"{elo[vid]: 7.2f}", YTDATA.videos.get(vid, vid))

	print('...')

	# Show bottom
	for vid in sortedKeys[-10:]:
		print(f"{elo[vid]: 7.2f}", YTDATA.videos.get(vid, vid))
	print()



################
##### MAIN #####
################


if __name__ == '__main__':

	# Unload parameters
	parser = argparse.ArgumentParser()
	parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
	parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json', type=str)
	parser.add_argument('-u', '--user', help='Get statistics for given user only. If unset, will compute global statistics', type=str, default=None)

	args = vars(parser.parse_args())

	cmpFile = ComparisonFile(args['tournesoldataset'])

	YTDATA = YTData()
	try:
		YTDATA.load(args['cache'])
	except FileNotFoundError:
		pass

	compute_elo_ranking(cmpFile, YTDATA, args['user'])
