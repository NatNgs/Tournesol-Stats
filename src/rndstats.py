import sys

import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData

def _print_statistics(nb_comps: dict[str, dict[str, int]]):
	# Aggregate
	nb_comparisons_by_criteria: dict[str, dict[int, int]] = dict() # Criteria, rank (how many comparisons), count (how many items have this many comparisons)
	for criteria in nb_comps:
		nb_comparisons_by_criteria[criteria]: dict[int, int] = dict()
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

def get_users_count_stats(cmpFile: ComparisonFile):
	nb_comparisons_by_user: dict[str, dict[str, int]] = dict() # Kind, user, count
	nb_comparisons_by_user['OVERALL'] = dict()

	def line_parser(line: ComparisonLine):
		if not line.criteria in nb_comparisons_by_user:
			nb_comparisons_by_user[line.criteria] = dict()

		if not line.user in nb_comparisons_by_user[line.criteria]:
			nb_comparisons_by_user[line.criteria][line.user] = 1
		else:
			nb_comparisons_by_user[line.criteria][line.user] += 1

		if not line.user in nb_comparisons_by_user['OVERALL']:
			nb_comparisons_by_user['OVERALL'][line.user] = 1
		else:
			nb_comparisons_by_user['OVERALL'][line.user] += 1

	cmpFile.foreach(line_parser)
	_print_statistics(nb_comparisons_by_user)

	return [user for user in nb_comparisons_by_user['largely_recommended'] if nb_comparisons_by_user['largely_recommended'][user] <= 1]

def get_videos_count_stats(cmpFile: ComparisonFile):
	nb_comparisons_by_video: dict[str, dict[str, int]] = dict() # Kind, video, count

	def line_parser(line: ComparisonLine):
		if not line.criteria in nb_comparisons_by_video:
			nb_comparisons_by_video[line.criteria] = dict()

		for vid in [line.vid1, line.vid2]:
			if not vid in nb_comparisons_by_video[line.criteria]:
				nb_comparisons_by_video[line.criteria][vid] = 1
			else:
				nb_comparisons_by_video[line.criteria][vid] += 1

	cmpFile.foreach(line_parser)
	_print_statistics(nb_comparisons_by_video)

def get_creators_stats(cmpFile: ComparisonFile, ignore_users: list[str]):
	nb_comparisons_by_channel: dict[str, dict[str, int]] = dict() # Kind, channel, count
	vids = set()

	def _video_lister(line: ComparisonLine):
		if line.user in ignore_users:
			return
		vids.add(line.vid1)
		vids.add(line.vid2)
	cmpFile.foreach(_video_lister)
	YTDATA = YTData()
	try:
		YTDATA.load('data/YTData_cache.json')
	except FileNotFoundError:
		pass
	YTDATA.update(vids, save='data/YTData_cache.json')

	def _line_parser(line: ComparisonLine):
		if line.user in ignore_users:
			return

		if not line.criteria in nb_comparisons_by_channel:
			nb_comparisons_by_channel[line.criteria] = dict()

		for vid in [line.vid1, line.vid2]:
			if not vid in YTDATA.videos:
				continue
			if not YTDATA.videos[vid].channel:
				continue

			channel = YTDATA.videos[vid].channel
			cname = channel['name'] or channel.id
			if not cname in nb_comparisons_by_channel[line.criteria]:
				nb_comparisons_by_channel[line.criteria][cname] = 1
			else:
				nb_comparisons_by_channel[line.criteria][cname] += 1
	cmpFile.foreach(_line_parser)

	_print_statistics(nb_comparisons_by_channel)


def get_user_specific_stats(cmpFile: ComparisonFile, user: str):
	criteria_values: dict[str, list[int]] = dict() # {criteria: [<int>, .. (index=10)<int>]}

	def line_parser(line: ComparisonLine):
		if line.user != user:
			return

		if not line.criteria in criteria_values:
			criteria_values[line.criteria] = [0]*11

		criteria_values[line.criteria][int(np.abs(line.score))] += 1

	cmpFile.foreach(line_parser)

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

if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) <= 1:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir> (<prefUser>)
	dataDir:
		Directory where the public dataset is located
		(ex: data/input/tournesol_dataset)
	prefUser: (Optional)
		User from whom get user specific statistics
		(ex: NatNgs)
""")
		exit(-1)

	input_dir = sys.argv[1]

	cmpFile = ComparisonFile(input_dir)

	print("### User Statistics ###")
	users_with_only_1cmp = get_users_count_stats(cmpFile)
	print
	print("### Videos Statistics ###")
	get_videos_count_stats(cmpFile)
	print
	print("### Channels Statistics ###")
	get_creators_stats(cmpFile, users_with_only_1cmp)
	print

	if len(sys.argv) > 2:
		user = sys.argv[2]
		print(f"### {user} Statistics ###")
		get_user_specific_stats(cmpFile, user)
		print

