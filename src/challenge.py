import argparse
from datetime import datetime
from dateutil.parser import isoparse

import math
import pytz
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData
from model.collectivecriteriascores import CollectiveCriteriaScoresFile
from model.individualcriteriascores import IndividualCriteriaScoresFile

MIN_USERS = 3 # If no user specified: Video compared by less than x different users are excluded
MAX_USERS = 15 # If no user specified: Video compared by more than x different users are excluded
MIN_CMPS = 5 # If user specified: Video having less than x comparisons are excluded
MAX_CMPS = 9 # If user specified: Video having more than x comparisons are excluded

def d2(a,b):
	return sum((ab[0]-ab[1])**2 for ab in zip(a,b))

def compute_needs_for_challenge(dataset: str, YTDATA: YTData, user: str, fetch_path: str, langs:set[str], count:int):
	cmpFile = ComparisonFile(dataset)
	ccsf = IndividualCriteriaScoresFile(dataset) if user else CollectiveCriteriaScoresFile(dataset)

	vid_cmps: dict[str,set[str]] = dict()
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

		vid_cmps.setdefault(line.vid1, set()).add(line.vid2)
		vid_cmps.setdefault(line.vid2, set()).add(line.vid1)
	cmpFile.foreach(build_vid_votes)


	# Remove if less than 3 different users, or 5 comparisons
	for vid in list(vid_usrs.keys()):
		toRemove=False
		if user: # Challenging on a specific user
			if len(vid_votes[vid]) < MIN_CMPS or len(vid_votes[vid]) > MAX_CMPS:
				toRemove=True
		else: # Challenging global
			if len(vid_usrs[vid]) < MIN_USERS or len(vid_usrs[vid]) > MAX_USERS:
				toRemove=True

		if toRemove:
			vid_votes.pop(vid)
			vid_usrs.pop(vid)
			vid_cmps.pop(vid)
		else:
			vid_votes[vid].sort()


	if fetch_path:
		YTDATA.update(vids=vid_votes.keys(), save=fetch_path)

	for vid in list(vid_votes.keys()):
		# Filter if video data not retrieved
		if not vid in YTDATA.videos or not YTDATA.videos[vid]['title']:
			vid_votes.pop(vid)
			continue
		# Filter by language
		lng = YTDATA.videos[vid].get('defaultLng', '??')
		if langs and (not lng in langs):
			vid_votes.pop(vid)

	# Aggregate data to "Need to be challenged" score
	gScores = (
		ccsf.get_scores(criterion='largely_recommended', users=[user], vids=vid_votes.keys())[user] if user else # (score, uncertainty) = gscores[vid]['largely_recommended']
		ccsf.get_scores(criterion='largely_recommended', vids=vid_votes.keys()) # (score, uncertainty) = gscores[vid]['largely_recommended']
	)

	now = datetime.utcnow().replace(tzinfo=pytz.UTC)
	vid_values: dict[str, float] = {
		v: (
			gScores[v]['largely_recommended'][0], # Score largely_recommended
			math.sqrt(YTDATA.videos[v]['duration']), # Durée de la video
			math.sqrt((now - isoparse(YTDATA.videos[v]['date'])).days), # Date de sortie
		)
		for v,vv in vid_votes.items()
		if (v in gScores and gScores[v]['largely_recommended'][0] > 0) # and min(vv) >= 0)
		 	or user #and max(vv) <= 0)
	}
	print('Videos to be challenged:', len(vid_values))

	final = sorted(vid_values.keys(), key=vid_values.get, reverse=True)

	total = 0
	already = set()
	pairs:list[tuple[float,str,str]] = [] # d2,v1,v2
	for vid in final:
		if vid in already:
			continue
		already.add(vid)

		# Against who ?
		ordrd = sorted(
			(
				v2 for v2 in final
				# v2 hasn't been returned yet
				if v2 not in already
				# v1 & v2 are in same language
				and YTDATA.videos[vid].get('defaultLng', '??') == YTDATA.videos[v2].get('defaultLng', '??')
				# no comparisons between v1 <-> v2
				and v2 not in vid_cmps[vid]
				# there are users having seen both v1 & v2
				and vid_usrs[vid].intersection(vid_usrs[v2])
				# no comparison between v1 <-> any other video <-> v2
				and (not vid_cmps[vid].intersection(vid_cmps[v2]))
			),
			key=lambda v2: d2(vid_values[vid],vid_values[v2]),
			reverse=False
		)
		if not ordrd:
			break

		total += len(ordrd)
		against = ordrd[0]
		already.add(against)
		pairs.append((d2(vid_values[vid],vid_values[against]),vid,against))

	print(f"Available pairs to be suggested: {total/2:.0f}")

	pairs.sort()
	print()
	for i,p in enumerate(pairs[:count]):
		_d2 = p[0]
		vid = p[1]
		against = p[2]

		score1 = gScores[vid]['largely_recommended'][0]
		score2 = gScores[against]['largely_recommended'][0]
		len1 = YTDATA.videos[vid]['duration']/60
		len2 = YTDATA.videos[against]['duration']/60
		since1 = YTDATA.videos[vid]['date']
		since2 = YTDATA.videos[against]['date']

		print(f"{i+1:2d}. https://tournesol.app/comparison?uidA=yt:{vid}&uidB=yt:{against}   (similarity={1/math.sqrt(_d2+1):.0%})")
		print(f"- {str(YTDATA.videos.get(vid, vid))}")
		print(f"    - {score1:+5.1f}🌻 ({len(vid_votes[vid])} cmps / {len(vid_usrs[vid])} users), {since1[:10]}, {len1:.0f}min")
		print(f"- {str(YTDATA.videos.get(against, against))}")
		print(f"    - {score2:+5.1f}🌻 ({len(vid_votes[against])} cmps / {len(vid_usrs[against])} users), {since2[:10]}, {len2:.0f}min")
		print()

################
##### MAIN #####
################

def positiveInt(val):
	try:
		if int(val) > 0:
			return int(val)
	except:
		pass
	raise argparse.ArgumentTypeError(f"Expected a positive integer but value was: {val}")

# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json', type=str)
parser.add_argument('-l', '--lng', help='Video languages to keep. All languages enabled if unset. Use letters langage code ex: "en", "fr", "sp". Use "??" for videos of unknown language. Allow coma separated values to allow multiple like "fr,en,??"', default='', type=str)
parser.add_argument('-u', '--user', help='Get statistics for given user. If unset, will compute global statistics', type=str, default=None)
parser.add_argument('-n', '--nb', help='Number of how much suggestions to show (default: 10)', type=positiveInt, default=10)
parser.add_argument('--fetch', help='If set, will fetch youtube API for updating data', action=argparse.BooleanOptionalAction, default=False)

args = vars(parser.parse_args())

YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

compute_needs_for_challenge(
	args['tournesoldataset'],
	YTDATA,
	args['user'],
	args['cache'] if args['fetch'] else None,
	set(args['lng'].split(',')) if args['lng'] else None,
	args['nb']
)
