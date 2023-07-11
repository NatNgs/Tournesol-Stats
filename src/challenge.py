import argparse

import numpy as np
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData


def compute_needs_for_challenge(cmpFile: ComparisonFile, YTDATA: YTData, user: str, fetch_path: str, langs:set[str]):
	vid_votes: dict[str, list[int]] = dict()
	vid_usrs: dict[str, set[str]] = dict()

	# Gather data
	def build_vid_votes(line: ComparisonLine):
		if (user and line.user != user) or line.criteria != 'largely_recommended':
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
		if (not user and len(vid_usrs[vid]) < 3) \
				or (user and len(vid_votes[vid]) < 5):
			vid_votes.pop(vid)
		else:
			vid_votes[vid].sort()

	vid_usrs.clear()

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
	vid_values: dict[str, float] = {
		v: (-np.std(vv), np.average(vv), len(vv))
		for v,vv in vid_votes.items()
		if min(vv) > 0 or max(vv) < 0
	}

	final = sorted(vid_values.keys(), key=vid_values.get, reverse=True)

	def d2(x1,y1,x2,y2):
		return (x1-x2)**2+(y1-y2)**2

	already = set()
	print()
	i = 0
	while i < len(final) and len(already) < 10*2:
		vid = final[i]
		i += 1
		if vid in already:
			continue
		already.add(vid)

		std = -vid_values[vid][0]
		avg = vid_values[vid][1]

		# Against who ?

		ordrd = sorted((v2 for v2 in final[i+1:] if v2 not in already), key=lambda v2:
			d2(avg,std,vid_values[v2][1],-vid_values[v2][0]),
			reverse=False)
		if not ordrd:
			break
		against = ordrd[0]
		already.add(against)

		print(f"{len(already)/2:3.0f}.", YTDATA.videos.get(vid, vid))
		print(f"\tstd={std:.2f} avg={avg:+.1f}", vid_votes[vid])
		# print(f"  => ({d2(avg,std,vid_values[against][1],-vid_values[against][0]):.2f})", YTDATA.videos.get(against, against))
		print(f"  =>", YTDATA.videos.get(against, against))
		print(f"\tstd={-vid_values[against][0]:.2f} avg={vid_values[against][1]:+.1f}", vid_votes[against])
		print(f"    https://tournesol.app/comparison?uidA=yt:{vid}&uidB=yt:{against}")
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

cmpFile = ComparisonFile(args['tournesoldataset'])


YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

compute_needs_for_challenge(cmpFile, YTDATA, args['user'], args['cache'] if args['fetch'] else None, set(args['lng'].split(',')) if args['lng'] else None)
