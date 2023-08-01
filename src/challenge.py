import argparse

import math
import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData
from model.collectivecriteriascores import CollectiveCriteriaScoresFile
from model.individualcriteriascores import IndividualCriteriaScoresFile

MIN_USERS = 3 # If no user specified: Video compared by less than x different users are excluded
MIN_CMPS = 4 # If user specified: Video having less than x comparisons are excluded
MAX_CMPS = 7 # If user specified: Video having more than x comparisons are excluded

def compute_needs_for_challenge(dataset: str, YTDATA: YTData, user: str, fetch_path: str, langs:set[str]):
	cmpFile = ComparisonFile(dataset)
	ccsf = IndividualCriteriaScoresFile(dataset) if user else CollectiveCriteriaScoresFile(dataset)

	vid_votes: dict[str, list[int]] = dict()
	vid_usrs: dict[str, set[str]] = dict()

	# Gather data
	def build_vid_votes(line: ComparisonLine):
		if (user and line.user != user) or line.criterion != 'largely_recommended':
			return

		vid_votes.setdefault(line.vid1, [])
		vid_votes.setdefault(line.vid2, [])

		vid_votes[line.vid2].append(line.score)
		vid_votes[line.vid1].append(-line.score)

		vid_usrs.setdefault(line.vid1, set()).add(line.user)
		vid_usrs.setdefault(line.vid2, set()).add(line.user)
	cmpFile.foreach(build_vid_votes)


	# Remove if less than 3 different users, or 5 comparisons
	for vid in vid_usrs.keys():
		if user: # Challenging on a specific user
			if len(vid_votes[vid]) < MIN_CMPS or len(vid_votes[vid]) > MAX_CMPS:
				vid_votes.pop(vid)

		else: # Challenging global
			if len(vid_usrs[vid]) < 3:
				vid_votes.pop(vid)

		if vid in vid_votes:
			vid_votes[vid].sort()


	if fetch_path:
		YTDATA.update(vids=vid_votes.keys(), save=fetch_path)

	# Exclude languages other than EN, FR and unknown
	for vid in list(vid_votes.keys()):
		if not vid in YTDATA.videos or not YTDATA.videos[vid]['title']:
			vid_votes.pop(vid)
			continue
		lng = YTDATA.videos[vid].get('defaultLng', '??')
		if langs and (not lng in langs):
			vid_votes.pop(vid)

	# Aggregate data to "Need to be challenged" score
	gScores = (
		ccsf.get_scores(criterion='largely_recommended', users=[user], vids=vid_votes.keys())[user] if user else # (score, uncertainty) = gscores[vid]['largely_recommended']
		ccsf.get_scores(criterion='largely_recommended', vids=vid_votes.keys()) # (score, uncertainty) = gscores[vid]['largely_recommended']
	)

	vid_values: dict[str, float] = {
		v: (
			gScores[v]['largely_recommended'][0],
			math.sqrt(YTDATA.videos[v]['duration']),
		)
		for v,vv in vid_votes.items()
		if (gScores[v]['largely_recommended'][0] > 0 and min(vv) >= 0) \
			or (user and max(vv) <= 0)
	}

	final = sorted(vid_values.keys(), key=vid_values.get, reverse=True)

	def d2(a,b):
		return sum((ab[0]-ab[1])**2 for ab in zip(a,b))

	already = set()
	pairs:list[tuple[float,str,str]] = [] # d2,v1,v2
	for vid in final:
		if vid in already:
			continue
		already.add(vid)

		# Against who ?

		ordrd = sorted(
			(v2 for v2 in final if v2 not in already),
			key=lambda v2: d2(vid_values[vid],vid_values[v2]),
			reverse=False
		)
		if not ordrd:
			break

		against = ordrd[0]
		already.add(against)
		pairs.append((d2(vid_values[vid],vid_values[against]),vid,against))

	pairs.sort()
	print()
	for i,p in enumerate(pairs[:10]):
		_d2 = p[0]
		vid = p[1]
		against = p[2]
		(score1, len1) = vid_values[vid]
		(score2, len2) = vid_values[against]
		len1 = math.ceil((len1*len1)/60)
		len2 = math.ceil((len2*len2)/60)

		print(f"{i+1:2d}. https://tournesol.app/comparison?uidA=yt:{vid}&uidB=yt:{against}   (diff={_d2:.2f})")
		print(f"- {YTDATA.videos.get(vid, vid)}")
		print(f"    - {score1:+5.1f}🌻, {len1:3.0f}min ({len(vid_votes[vid])} cmps / {len(vid_usrs[vid])} users)")
		print(f"- {YTDATA.videos.get(against, against)}")
		print(f"    - {score2:+5.1f}🌻, {len2:3.0f}min ({len(vid_votes[against])} cmps / {len(vid_usrs[against])} users)")
		print()

################
##### MAIN #####
################


# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json', type=str)
parser.add_argument('-l', '--lng', help='Video languages to keep. All languages enabled if unset. Use letters langage code ex: "en", "fr", "sp". Use "??" for videos of unknown language. Allow coma separated values to allow multiple like "fr,en,??"', default='', type=str)
parser.add_argument('-u', '--user', help='Get statistics for given user. If unset, will compute global statistics', type=str, default=None)
parser.add_argument('--fetch', help='If set, will fetch youtube API for updating data', action=argparse.BooleanOptionalAction, default=False)

args = vars(parser.parse_args())

YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

compute_needs_for_challenge(args['tournesoldataset'], YTDATA, args['user'], args['cache'] if args['fetch'] else None, set(args['lng'].split(',')) if args['lng'] else None)
