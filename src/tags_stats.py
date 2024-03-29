import argparse
from model.collectivecriteriascores import CollectiveCriteriaScoresFile
from model.comparisons import ComparisonFile, ComparisonLine
from model.youtube_api import YTData

def group_keys(d: dict):
	return {frozenset([k for k in d.keys() if d[k] == n]): n for n in set(d.values())}


def get_vids_from_comparisons(tdata: str):
	# Extract videos id from comparisons
	# - Need to be compared by at least MIN_USERS different users
	# - users having compared at least MIN_CMPS different videos
	MIN_USERS=2
	MIN_CMPS=3

	cf = ComparisonFile(tdata)

	usrs_cmps: dict[str, set[str]] = dict()
	usrs_ok: set[str] = set()
	def line_parser_users(line: ComparisonLine):
		if line.criteria != 'largely_recommended':
			return
		if line.user in usrs_ok:
			return
		if not line.user in usrs_cmps:
			usrs_cmps[line.user] = set()
		usrs_cmps[line.user].add(line.vid1)
		usrs_cmps[line.user].add(line.vid2)
		if len(usrs_cmps[line.user]) >= MIN_CMPS:
			usrs_ok.add(line.user)
			usrs_cmps.pop(line.user)
	cf.foreach(line_parser_users)
	# free memory: flush users_cmps
	usrs_cmps.clear()

	vid_usr: dict[str,set[str]] = dict()
	vid_ok: set[str] = set()
	def line_parser_videos(line: ComparisonLine):
		if line.criteria != 'largely_recommended':
			return
		if line.user not in usrs_ok:
			return
		for v in [line.vid1, line.vid2]:
			if v in vid_ok:
				continue
			if not v in vid_usr:
				vid_usr[v] = set()
			vid_usr[v].add(line.user)
			if len(vid_usr[v]) >= MIN_USERS:
				vid_ok.add(v)
				vid_usr.pop(v)
	cf.foreach(line_parser_videos)

	return vid_ok


def do_analyse_tags(vids: set[str], ytdata: YTData, tds: str):
	print('Analysing', len(vids), 'videos')

	tags_vids: dict[str, set[str]] = dict()
	for vid in vids:
		vdata = ytdata.videos[vid]
		tags = set()
		if vdata.channel:
			tags.add('Channel: ' + vdata.channel.get('title', vdata['cid']))
		if vdata['category']:
			tags.add(f"YT Category: {vdata['category']}")
		if vdata['date']:
			tags.add(f"Year: {vdata['date'][:4]}")
		if vdata['tags']:
			tags.update(['Tag: ' + t for t in vdata['tags']])
		if vdata['topics']:
			tags.update(['Topic: ' + t for t in vdata['topics']])
		if vdata['localizations']:
			tags.update(['Locale: ' + t for t in vdata['localizations']])
		for t in tags:
			if not t in tags_vids:
				tags_vids[t] = set()
			tags_vids[t].add(vid)

	# Group tags if same vids
	grouped_tags_vids: dict[set[str], set[str]] = group_keys({k:frozenset(tags_vids[k]) for k in tags_vids})
	# Free some space
	tags_vids.clear()

	ccsf = CollectiveCriteriaScoresFile(tds)
	vid_scores: dict[str, float] = ccsf.get_vids_scores('largely_recommended', vids)

	MIN_VIDS_KEEP_TAG=3
	tags_scores: dict[str, float] = dict()
	for tag in list(grouped_tags_vids.keys()):
		g = set(grouped_tags_vids[tag]).intersection(vid_scores.keys())
		if len(g) < MIN_VIDS_KEEP_TAG:
			grouped_tags_vids.pop(tag)
			continue
		tags_scores[tag] = sum([vid_scores[v] for v in g]) / len(g)

	ordered = sorted(tags_scores.keys(), key=lambda k: tags_scores[k], reverse=True)
	print('Analyzed', len(ordered), 'distinct tags')

	for t in ordered:
		print(f"{tags_scores[t]:+4.0f}🌻 (/{len(grouped_tags_vids[t])} videos) {' / '.join(sorted(t))}")


##############
##   MAIN   ##
##############


# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json', type=str)
parser.add_argument('--fetch', help='If set, will not fetch youtube API for updating data', action=argparse.BooleanOptionalAction, default=True)

args = vars(parser.parse_args())

# Build YTData object
ytdata = YTData()
try:
	ytdata.load(args['cache'])
except FileNotFoundError as e:
	pass

# Extract videos id from comparisons
# - Need to be compared by at least 3 different users
vids = get_vids_from_comparisons(args['tournesoldataset'])

if args['fetch']:
	# Updating cache
	ytdata.update(vids, save=args['cache'])

# Exclude videos without ytdata
vids.intersection_update(ytdata.videos.keys())

# Analyse videos
do_analyse_tags(vids, ytdata, args['tournesoldataset'])
