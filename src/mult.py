import sys
import time
import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
import scripts.data_fetcher as data_fetcher

def findUsersWeights(cmpFile: ComparisonFile):
	users_values: dict[str, list[int]] = dict() # {uid: [0, 1, .. 10]}
	def parse_line(line: ComparisonLine):
		if line.criterion != 'largely_recommended' or line.user != 'NatNgs':
			return
		if not line.user in users_values:
			users_values[line.user] = [0]*11
		users_values[line.user][line.score if line.score > 0 else -line.score] += 1
	cmpFile.foreach(parse_line)

	# Ratio between 0 (always same vote) and 1 (all notes given the same amount of time)
	min_ratio = 1/(np.std([0,0,0,0,0,0,0,0,0,0,1])+1)
	users_ratios: dict[str, float] = dict() # {uid: ratio}
	for uid in list(users_values.keys()):
		# Remove users with less than 3 comparisons, and users using always same vote
		s = sum(users_values[uid])
		if s >= 3 and s > max(users_values[uid]):
			stddev = np.std([v/s for v in users_values[uid]])
			r = (1/(stddev+1) - min_ratio)/(1-min_ratio)
			if r > 0:
				users_ratios[uid] = r

	return users_ratios

def extractComparisons(cmpFile: ComparisonFile):

	users = findUsersWeights(cmpFile)
	cmps: dict[str, dict[str, tuple[float, float]]] = dict() # {vid: {vid2: (sum, count)}}

	def parse_line(line: ComparisonLine):
		if line.criterion != 'largely_recommended' or (not line.user in users):
			return

		if not line.vid1 in cmps:
			cmps[line.vid1] = dict()
		if not line.vid2 in cmps:
			cmps[line.vid2] = dict()
		cmpVid1 = cmps[line.vid1]
		cmpVid2 = cmps[line.vid2]
		if not line.vid1 in cmpVid2:
			cmpVid2[line.vid1] = (0, 0)
		if not line.vid2 in cmpVid1:
			cmpVid1[line.vid2] = (0, 0)

		w = users[line.user]
		cmpVid1[line.vid2] = (cmpVid1[line.vid2][0]-line.score*w, cmpVid1[line.vid2][1]+w)
		cmpVid2[line.vid1] = (cmpVid2[line.vid1][0]+line.score*w, cmpVid2[line.vid1][1]+w)
	cmpFile.foreach(parse_line)

	# Remove vid with less than 2 comparisons
	l = len(cmps.keys())
	toredo = True
	while toredo:
		toredo = False
		for vid in list(cmps.keys()):
			if len(cmps[vid].keys()) <= 1:
				cmps.pop(vid, None)
				for sub in cmps.values():
					sub.pop(vid, None)
				toredo = True

	print(f"Total: {l}, Kept for analysis: {len(cmps.keys())}")

	return cmps


def affine_score(cmps: dict[str, dict[str, tuple[float, float]]], scores: dict[str, float]):
	newscores: dict[str, float] = dict()
	for vid in cmps:
		#if vid == 'Ot00MptJ4xs':
		#	print(f"{vid} ({scores[vid]:.0%})")
		pts = 0
		wgt = 0
		for vid2 in cmps[vid]:
			dif = cmps[vid][vid2][0]/cmps[vid][vid2][1] # Target difference
			tgt = scores[vid2] * (2**(dif/10)) # -10: Want to be 2x less; 10: want to be 2x more
			# tgt = scores[vid2] + dif # Target score
			pts += tgt * cmps[vid][vid2][1] # Weighted target score
			wgt += cmps[vid][vid2][1] # Weight

			#if vid == 'Ot00MptJ4xs':
			#	print(f"\t{vid2} ({scores[vid2]:.0%}) diff:{dif:.1f} {tgt:.0%} {cmps[vid][vid2][1]:.2f}")

		newscores[vid] = pts/wgt

	# Remap to [0,1]
	m = min(newscores.values())
	mm = max(newscores.values()) - m
	for vid in newscores:
		newscores[vid] = (newscores[vid]-m)/mm

	return newscores


if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) <= 1:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir>
	dataDir:
		Directory where the public dataset is located
		(ex: /data/input/tournesol_export_2023mmddThhmmssZ)
""")
		exit(-1)

	input_dir = sys.argv[1]

	cmps: dict[str, dict[str, tuple[float, float]]] = extractComparisons(ComparisonFile(input_dir)) # {vid: {vid2: (sum, count)}}

	scores: dict[str, float] = dict()
	for vdata in cmps:
		vdata = cmps[vdata].values()
		pts = sum([tpl[0] for tpl in vdata])
		wgt = sum([tpl[1] for tpl in vdata])
		scores[vdata] = ((pts/wgt + 10) / 20) # [-10,10] > [0,1]

	for i in range(10):
		newscores = affine_score(cmps, scores)
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
		print(f"Affinement {i}: updated {diff:0.2%} (max: {max_diff:0.2%})")
		if max_diff < 0.0001:
			break
		time.sleep(5)


	# # # Print # # #

	sorted_vids = list(scores.keys())
	sorted_vids.sort(key=lambda x: -scores[x])
	VIDEOS = data_fetcher.fetch_list(sorted_vids, True)

	for vdata in sorted_vids:
		if vdata in VIDEOS:
			print(f"{scores[vdata]:0.2%} {VIDEOS[vdata]}")
		else:
			print(f"{scores[vdata]:0.2%} [{vdata}]")
	print('\t...')
	#
	#for vid in sorted_vids[-10:]:
	#	if vid in VIDEOS:
	#		print(f"{scores[vid]:0.2%} {VIDEOS[vid]}")
	#	else:
	#		print(f"{scores[vid]:0.2%} [{vid}]")
