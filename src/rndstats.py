import argparse
from datetime import datetime, timedelta

import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData

MAX_UPDATE = 2500

def _print_statistics(nb_comps: dict[str, dict[str, int]]):
	# Aggregate
	nb_comparisons_by_criteria: dict[str, dict[int, int]] = dict() # Criteria, rank (how many comparisons), count (how many items have this many comparisons)
	for criteria in nb_comps:
		nb_comparisons_by_criteria[criteria] = dict()
		for count in nb_comps[criteria].values():
			if not count in nb_comparisons_by_criteria[criteria]:
				nb_comparisons_by_criteria[criteria][count] = 1
			else:
				nb_comparisons_by_criteria[criteria][count] += 1

	print()
	for criteria in nb_comparisons_by_criteria:
		itemcount = len(nb_comps[criteria])

		nbcomp_criteria = nb_comparisons_by_criteria[criteria]
		cumulated_nbcomp = [0]
		m = max(nbcomp_criteria.keys())
		for rnk in range(1, m+1):
			if rnk in nbcomp_criteria:
				cumulated_nbcomp.append(cumulated_nbcomp[-1] + nbcomp_criteria[rnk])
			else:
				cumulated_nbcomp.append(cumulated_nbcomp[-1])
		while cumulated_nbcomp[-1] == 0:
			cumulated_nbcomp.pop(-1)

		# nbusers = nbcomparisons
		keys = sorted(nbcomp_criteria.keys(), reverse=True)
		rnk = 0
		same_rnk = 0
		try:
			while same_rnk < keys[rnk]:
				same_rnk = same_rnk + (nbcomp_criteria.get(keys[rnk], 0))
				rnk += 1
		except IndexError as e:
			print(keys)
			print(rnk)
			print(same_rnk)
			raise e


		print(criteria, f"(over {itemcount})")

		print(f"\t- {cumulated_nbcomp[1]:5} have only 1 comparison ({cumulated_nbcomp[1]/itemcount:0.1%})")
		print(f"\t- {cumulated_nbcomp[same_rnk]-cumulated_nbcomp[1]:5} have 2 to {same_rnk-1} comparisons ({(cumulated_nbcomp[same_rnk]-cumulated_nbcomp[1])/itemcount:0.1%})")
		print(f"\t- {same_rnk:5} have {same_rnk} to {len(cumulated_nbcomp)-1} comparisons ({same_rnk/itemcount:0.1%})")

		print()

def print_users_count_stats(cmpFile: ComparisonFile):
	print("### Users Statistics ###")
	nb_comparisons_by_user: dict[str, dict[str, int]] = dict() # Kind, user, count
	nb_comparisons_by_user['OVERALL'] = dict()
	users_videos: dict[str,set[str]] = dict()
	users_active: set[str] = set()
	last_4weeks = datetime.today() - timedelta(weeks=4.5)

	def line_parser(line: ComparisonLine):
		if not line.criterion in nb_comparisons_by_user:
			nb_comparisons_by_user[line.criterion] = dict()

		if not line.user in nb_comparisons_by_user[line.criterion]:
			nb_comparisons_by_user[line.criterion][line.user] = 1
		else:
			nb_comparisons_by_user[line.criterion][line.user] += 1

		if not line.user in nb_comparisons_by_user['OVERALL']:
			nb_comparisons_by_user['OVERALL'][line.user] = 1
		else:
			nb_comparisons_by_user['OVERALL'][line.user] += 1

		if not line.user in users_videos:
			users_videos[line.user] = set()
		users_videos[line.user].add(line.vid1)
		users_videos[line.user].add(line.vid2)

		if datetime.fromisoformat(line.date) >= last_4weeks:
			users_active.add(line.user)


	cmpFile.foreach(line_parser)
	_print_statistics(nb_comparisons_by_user)

	topusers = sorted(nb_comparisons_by_user['largely_recommended'].keys(), key=nb_comparisons_by_user['largely_recommended'].get, reverse=True)
	print('Top 100 active users (by total recommendations count - having at least 1cmp in the last 4 weeks):')
	for i,u in enumerate(topusers[:100]):
		print(f"-{i+1:3d}. {u} ({len(users_videos[u])} videos / {nb_comparisons_by_user['largely_recommended'][u]} recommendations / {nb_comparisons_by_user['OVERALL'][u]} comparisons)")


def print_videos_count_stats(cmpFile: ComparisonFile):
	print("### Videos Statistics ###")
	nb_comparisons_by_video: dict[str, dict[str, int]] = dict() # Kind, video, count

	def line_parser(line: ComparisonLine):
		if not line.criterion in nb_comparisons_by_video:
			nb_comparisons_by_video[line.criterion] = dict()

		for vid in [line.vid1, line.vid2]:
			if not vid in nb_comparisons_by_video[line.criterion]:
				nb_comparisons_by_video[line.criterion][vid] = 1
			else:
				nb_comparisons_by_video[line.criterion][vid] += 1

	cmpFile.foreach(line_parser)
	_print_statistics(nb_comparisons_by_video)

def print_creators_stats(cmpFile: ComparisonFile, YTDATA: YTData, fetchunknown: bool):
	print("### Channels Statistics ###")
	nb_comparisons_by_channel: dict[str, dict[str, int]] = dict() # Kind, channel, count

	vids = set()
	def _video_lister(line: ComparisonLine):
		vids.add(line.vid1)
		vids.add(line.vid2)
	cmpFile.foreach(_video_lister)

	if fetchunknown:
		YTDATA.update(vids, save='data/YTData_cache.json', cachedDays=122, max_update=MAX_UPDATE)

	unknownvid = set()
	def _line_parser(line: ComparisonLine):
		if not line.criterion in nb_comparisons_by_channel:
			nb_comparisons_by_channel[line.criterion] = dict()

		for vid in [line.vid1, line.vid2]:
			if not vid in YTDATA.videos or not YTDATA.videos[vid].channel:
				unknownvid.add(vid)
				continue

			channel = YTDATA.videos[vid].channel
			cname = channel['name'] or channel.id
			if not cname in nb_comparisons_by_channel[line.criterion]:
				nb_comparisons_by_channel[line.criterion][cname] = 1
			else:
				nb_comparisons_by_channel[line.criterion][cname] += 1
	cmpFile.foreach(_line_parser)

	if unknownvid:
		print(f"  Analysed: {len(vids) - len(unknownvid)}/{len(vids)} videos (Some data missing from YTData cache)")

	_print_statistics(nb_comparisons_by_channel)


def print_global_stats(cmpFile: ComparisonFile, cache: YTData, fetchunknown: bool):
	print_users_count_stats(cmpFile)
	print
	print_videos_count_stats(cmpFile)
	print
	print_creators_stats(cmpFile, cache, fetchunknown)
	print


def print_user_specific_stats(cmpFile: ComparisonFile, YTDATA: YTData, user: str, fetchunknown: bool):
	print(f"### {args['user']} Statistics ###")
	criteria_values: dict[str, list[int]] = dict() # {criteria: [<int>, .. (index=10)<int>]}

	def line_parser(line: ComparisonLine):
		if line.user != user:
			return

		if not line.criterion in criteria_values:
			criteria_values[line.criterion] = [0]*11

		criteria_values[line.criterion][int(np.abs(line.score))] += 1

	cmpFile.foreach(line_parser)

	if fetchunknown:
		YTDATA.update(criteria_values.keys(), save='data/YTData_cache.json', cachedDays=122, max_update=MAX_UPDATE)

	print
	print(f'##### {user} stats #####')
	print
	for criteria in criteria_values:
		print(f"{criteria}:\n\t", end='')
		t_sum = sum(criteria_values[criteria])
		for rnk in range(11):
			print(f"[{rnk}]{(criteria_values[criteria][rnk])/t_sum:3.0%}, ", end='')
		print('\n')

	print('# Overall: #\n\t', end='')
	t_sum = sum([sum(criteria_values[criteria]) for criteria in criteria_values])
	for rnk in range(11):
		s = sum([criteria_values[criteria][rnk] for criteria in criteria_values])
		print(f"[{rnk}]{s/t_sum:3.0%}, ", end='')

	print('\n')


################
##### MAIN #####
################


# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json', type=str)
parser.add_argument('-u', '--user', help='Get statistics for given user. If unset, will compute global statistics', type=str, default=None)
parser.add_argument('--fetch', help='If set, will fetch youtube API for updating data', action=argparse.BooleanOptionalAction, default=False)

args = vars(parser.parse_args())

cmpFile = ComparisonFile(args['tournesoldataset'])

YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

if args['user']:
	print_user_specific_stats(cmpFile, YTDATA, args['user'], args['fetch'])
else:
	print_global_stats(cmpFile, YTDATA, args['fetch'])
