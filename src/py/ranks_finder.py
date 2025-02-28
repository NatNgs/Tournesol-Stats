import argparse
import math
import time
import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from dao.youtube_api import YTData

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

def find_ranks(cmps):
	# Find fixed TOP scores
	top = set()
	todo = set()
	for v1 in cmps:
		pos = True
		for v2 in cmps[v1]:
			if cmps[v1][v2][0] <= 0:
				pos = False
				break
		if pos:
			top.add(v1)
		else:
			todo.add(v1)
	topranks = ranker(top, todo, cmps) # (ranked, not_ranked)
	print('\tTop: ', len(topranks))

	# Find fixed BOTTOM scores
	bottom = set()
	for v1 in list(todo):
		neg = True
		for v2 in cmps[v1]:
			if cmps[v1][v2][0] >= 0:
				neg = False
				break
		if neg:
			bottom.add(v1)
			todo.remove(v1)
	bottomranks = ranker(bottom, topranks[1], cmps, reversed=True)
	print('\tBottom: ', len(bottom))

	unknownindex = len(topranks)
	if todo or bottomranks:
		topranks.append(todo)
		bottomranks.reverse()
		topranks.extend(bottomranks)
	return (topranks, unknownindex)


def ranker(top:set[str], todo:set[str], cmps:dict[str,dict[str,tuple[float,float]]], reversed=False):
	ranked:list[set[str]] = [top]
	ranks:dict[str,int] = {vid:0 for vid in top}

	advanced=True
	while advanced:
		advanced = False
		if ranked[-1]:
			ranked.append(set())
		for v1 in list(todo):
			not_yet = False
			for v2,sum_cnt in cmps[v1].items():
				if ((not reversed and sum_cnt[0] < 0) or (reversed and sum_cnt[0] > 0)) and (not v2 in ranks or v2 in ranked[-1]):
					not_yet = True
					break
			if not not_yet:
				todo.remove(v1)
				ranks[v1] = len(ranked)-1
				ranked[ranks[v1]].add(v1)
				advanced = True

	if not ranked[-1]:
		ranked.pop()
	return ranked


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

	(ranked,unknownIndex) = find_ranks(cmps)
	print(f"{len(ranked)} ranks, {unknownIndex} videos unable to be ranked\n")

	ranks={vid:i for i,vids in enumerate(ranked) for vid in vids}

	# # # Print # # #

	for rnk,vids in enumerate(ranked):
		if rnk == unknownIndex:
			print('#### Not Ranked')
		else:
			print(f"#### RANK {rnk}")
		for vid in vids:
			#dta = ', '.join(f"{ranks.get(i, '?')}({cmps[vid][i][0]:+d})" for i in cmps[vid] if (rnk < unknownIndex and ranks.get(i, -1) <= rnk) or (rnk > unknownIndex and ranks.get(i, -1) >= rnk))
			#if dta:
			#	print(f"\t- [{vid}] {YTDATA.videos.get(vid, vid)}\n\t\t{dta}")
			#else:
				print(f"\t- [{vid}] {YTDATA.videos.get(vid, vid)}")
