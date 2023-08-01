import argparse
import time
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
	cmpFile.foreach(parse_line)

	# Remove vid with less than 3 comparisons
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

	print(f"Total: {l}, Kept for analysis: {len(cmps)}")

	return cmps


def update_scores(cmps: dict[str, dict[str, tuple[float, float]]], scores: dict[str, float], fixed: set[str]):
	newscores: dict[str, float] = dict()

	for vid in cmps:
		if vid in fixed:
			newscores[vid] = scores[vid]
			continue

		mmx:int = max(abs(cmps[vid][v2][0]) for v2 in cmps[vid]) # maximum of absolute values of votes (0 to 10)
		if mmx == 0:
			# All votes are zero, move this score to average of his comparisons votes
			newscores[vid] = np.average([scores[v2] for v2 in cmps[vid]], weights=[cmps[vid][v2][1] for v2 in cmps[vid]])
			continue

		s = scores[vid]
		furth:float = max(abs(scores[v2]-s) for v2 in cmps[vid]) # furthest distance from vid score and others
		if furth < 0.01:
			furth = 0.01 # Minimum twitching
		elif furth > 0.5:
			furth = 0.5 # Maximum twitching

		# Say that furthest distance == maximum aboslute value
		dist_per_point = furth/mmx

		pts = 0.0
		wgt = 0.0
		for v2 in cmps[vid]:
			pts += max(-1, min(1, scores[v2] + cmps[vid][v2][0] * dist_per_point)) * cmps[vid][v2][1]
			wgt += cmps[vid][v2][1]

		newscores[vid] = pts/wgt

	return newscores



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


	for i in range(100*len(scores)):
		# Update score
		newscores = update_scores(cmps, scores, fixed)

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
		if i%25 == 0:
			print(f"Update {i+1}: updated {diff:0.2%} (max: {max_diff:0.2%})", flush=True)
		if max_diff < 0.0001:
			print(f"Update {i+1}: updated {diff:0.2%} (max: {max_diff:0.2%})", flush=True)
			break


	# # # Print # # #

	sorted_vids: list[str] = sorted(scores.keys(), key=scores.get, reverse=True)

	for vid in sorted_vids:
		if vid in fixed:
			print(f"#### {YTDATA.videos.get(vid, vid)}")
		else:
			print(f"{scores[vid]:+4.0%} {YTDATA.videos.get(vid, vid)}")
