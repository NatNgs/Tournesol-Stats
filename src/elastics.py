import argparse
import math
from datetime import datetime
import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData

def extractComparisons(cmpFile: ComparisonFile, user: str):

	cmps: dict[str, dict[str, tuple[float, float, set[str]]]] = dict() # {vid: {vid2: (sum, count)}}
	usrs: dict[str,set[str]] = dict() # {vid: {usr1, usr2, ...}}

	def parse_line(line: ComparisonLine):
		if line.criterion != 'largely_recommended' or (user and user != line.user):
			return

		if not line.vid1 in cmps:
			cmps[line.vid1] = dict()
		if not line.vid2 in cmps:
			cmps[line.vid2] = dict()
		cmpVid1 = cmps[line.vid1]
		cmpVid2 = cmps[line.vid2]
		if not line.vid1 in cmpVid2:
			cmpVid2[line.vid1] = (0, 0, set())
		if not line.vid2 in cmpVid1:
			cmpVid1[line.vid2] = (0, 0, set())

		if not user:
			usrs.setdefault(line.vid1, set()).add(line.user)
			usrs.setdefault(line.vid2, set()).add(line.user)

		cmpVid1[line.vid2] = (cmpVid1[line.vid2][0]-line.score, cmpVid1[line.vid2][1]+1)
		cmpVid2[line.vid1] = (cmpVid2[line.vid1][0]+line.score, cmpVid2[line.vid1][1]+1)
	print('Extracting comparisons...')
	cmpFile.foreach(parse_line)

	# Remove vid with less than 3 comparisons or 5 users
	print('Filtering comparisons...')
	l = len(cmps)
	toredo = True
	while toredo:
		toredo = False
		for vid in list(cmps.keys()):
			if not user and len(usrs[vid]) < 3:
				cmps.pop(vid, None)
				for sub in cmps.values():
					sub.pop(vid, None)
				toredo = True
			elif len(cmps[vid]) < 3:
				cmps.pop(vid, None)
				for sub in cmps.values():
					sub.pop(vid, None)
				toredo = True

	print(f"Videos kept for analysis: {len(cmps)}")
	return cmps


def update_scores_v1(cmps: dict[str, dict[str, tuple[float, float]]], scores: dict[str, float], fixed: set[str], power:float):
	newscores: dict[str, float] = dict()

	for vid in cmps:
		if vid in fixed:
			newscores[vid] = scores[vid]
			continue

		s1 = scores[vid]
		move=0
		div=1
		for v2,sum_cnt in cmps[vid].items():
			s2 = scores[v2]
			w = sum_cnt[1]*power
			if np.sign(sum_cnt[0]) != np.sign(s1-s2):
				move += w* (sum_cnt[0]/10)
			div += w

		if div > 0:
			newscores[vid] = s1 + move/div
		else:
			newscores[vid] = scores[vid]

	return newscores



def update_scores_v2(cmps: dict[str, dict[str, tuple[float, float]]], scores: dict[str, float], fixed: set[str], power:float):
	newscores: dict[str, float] = dict()

	for vid in cmps:
		if vid in fixed:
			newscores[vid] = scores[vid]
			continue

		# Group comparisons in 3 groups: under/equal/higher
		under = list()
		equal = list()
		higher = list()
		for v2,sum_cnt in cmps[vid].items():
			dist = (scores[v1] - scores[v2]) # Between -2 & +2
			avgvote = (sum_cnt[0]/sum_cnt[1]) # Between -10 & +10: expected direction & "length" of the distance
			expt_dist = avgvote**3/1000 # Between -1 & +1
			expt_note = np.clip(scores[v2] + expt_dist, -.99, .99)
			force = sum_cnt[1] / math.sqrt(math.exp(expt_dist - dist)) # increases if many votes OR if distance if far from expected

			(equal if avgvote == 0 else higher if avgvote > 0 else under).append( (expt_note, force) )

		current_score = scores[vid]
		moved_score = np.average([
			(sum(v[0]*v[1] for v in l) / sum(v[1] for v in l))
			for l in [under, equal, higher]
			if l
		])

		newscores[vid] = (current_score*(1-power)) + (moved_score*power)

	return newscores



################
##### MAIN #####
################


if __name__ == '__main__':

	# Unload parameters
	parser = argparse.ArgumentParser()
	parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
	parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json.gz', type=str)
	parser.add_argument('-u', '--user', help='Get statistics for given user only. If unset, will compute global statistics', type=str, default=None)

	args = vars(parser.parse_args())

	cmpFile = ComparisonFile(args['tournesoldataset'])

	YTDATA = YTData()
	try:
		YTDATA.load(args['cache'])
	except FileNotFoundError:
		pass

	cmps: dict[str, dict[str, tuple[float, float]]] = extractComparisons(cmpFile, args['user']) # {vid: {vid2: (sum, count)}}

	scores: dict[str, float] = dict()

	# Videos with fixed scores (having only positive or only negative votes)
	fixed = set() # fixed vids list
	for v1 in cmps:
		pos = False
		zer = False
		neg = False
		for v2 in cmps[v1]:
			if cmps[v1][v2][0] > 0:
				pos = True
				if neg:
					break
			elif cmps[v1][v2][0] < 0:
				neg = True
				if pos:
					break
			else:
				zer = True
				break
		# Init scores
		if zer or (pos and neg):
			vdata = cmps[v1].values()
			pts = sum([tpl[0] for tpl in vdata])
			wgt = sum([tpl[1] for tpl in vdata])
			scores[v1] = (pts/wgt)/10 # [-10,10] > [-1,1]
		else:
			# Fix score to 1 for fixed positives; -1 to fixed negatives
			fixed.add(v1)
			scores[v1] = 1 if pos else -1

	minmax = 999
	t1 = datetime.now()
	i = 0
	for i in range(len(scores)**2):
		# Update score
		newscores = update_scores_v2(cmps, scores, fixed, 1/math.sqrt(i+1))

		# Compute & print difference
		diff = 0
		max_diff = 0
		for key in scores:
			dif = (scores[key] - newscores[key])
			if dif < 0:
				dif = -dif
			diff += dif
			if dif > max_diff:
				max_diff = dif
		scores = newscores

		if max_diff < minmax:
			minmax = max_diff

		t2 = datetime.now()
		if (t2 - t1).seconds >= 1:
			print(f"Update {i+1}: updated {diff:0.2%} (max: {max_diff:0.2%} - min: {minmax:0.2%})")
			t1 = t2
		if max_diff < 0.001:
			break

	print(f"Update {i+1}: updated {diff:0.2%} (max: {max_diff:0.2%})")


	# # # Print # # #

	sorted_vids: list[str] = sorted(scores.keys(), key=scores.get, reverse=True)

	for vid in sorted_vids:
		if vid in fixed:
			print(f"#### {YTDATA.videos.get(vid, vid)}")
		else:
			dta = ', '.join(f"{d[0]:+.0f}{d[1]:+.0f}"
				for d in
					sorted((scores[v]*100, vv[0]) for v,vv in cmps[vid].items())
			)
			print(f"{scores[vid]:+4.0%} {YTDATA.videos.get(vid, vid)}\n\t({dta})")
