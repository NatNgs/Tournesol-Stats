import sys
from model.comparisons import ComparisonFile, ComparisonLine
import networkx as nx

from model.youtube_api import YTData

def recom(user: str, cmp_file: ComparisonFile, langs: set[str]):
	# Separate videos rated by me from others
	users_vids: set[str] = set()
	vid_to_recommend: set[str] = set()

	uncertain_users: dict[str, ComparisonLine] = dict() # user: (vid1, vid2)
	validated_users: set[str] = set()

	graph = nx.Graph()

	def _parse_lines(line: ComparisonLine):
		if line.criteria != 'largely_recommended':
			return

		if line.user == user:
			users_vids.add(line.vid1)
			users_vids.add(line.vid2)
			graph.add_edge(line.vid1, line.vid2)
			return

		if line.user in uncertain_users:
			validated_users.add(line.user)
			_parse_lines(uncertain_users.pop(line.user))
		elif line.user not in validated_users:
			uncertain_users[line.user] = line
			return
		# Below: Validated other users

		if not line.vid1 in users_vids:
			vid_to_recommend.add(line.vid1)
		if not line.vid2 in users_vids:
			vid_to_recommend.add(line.vid2)
		graph.add_edge(line.vid1, line.vid2)

	cmp_file.foreach(_parse_lines)


	# Exclude users with only one 'largely_recommended' comparison
	print(f"Purged {len(uncertain_users)}/{len(validated_users)+len(uncertain_users)} users having only one comparison")
	uncertain_users.clear()
	validated_users.clear()
	print(graph)

	YTDATA = YTData()
	try:
		YTDATA.load('data/YTData_cache.json')
	except FileNotFoundError:
		pass
	YTDATA.update(users_vids | vid_to_recommend, save='data/YTData_cache.json')

	# Exclude videos not in VIDEOS list
	vids = set(YTDATA.videos.keys())

	lngth_before = len(vid_to_recommend)
	to_remove = vid_to_recommend.difference(vids)
	graph.remove_nodes_from(to_remove)
	vid_to_recommend.intersection_update(vids)
	print(f"Removed {lngth_before-len(vid_to_recommend)} videos not found by youtube fetch")

	# Exclude videos not in known language
	lngth_before = len(vid_to_recommend)
	print(lngth_before, 'remaining')
	for vid in list(vid_to_recommend):
		lang = set(YTDATA.videos[vid]['localizations'] or [])
		if not lang or not lang.intersection(langs):
			graph.remove_node(vid)
			vid_to_recommend.remove(vid)
	print(f"Removed {lngth_before-len(vid_to_recommend)} videos from channel not in accepted languages")


	# Exclude top 80% videos (by recommendation nb)
	degree_list: list[tuple[str, int]] = [tpl for tpl in graph.degree() if not tpl[0] in users_vids] # [(vid, degree)]
	degree_list.sort(key=lambda tpl: tpl[1], reverse=True)
	cut = int(len(degree_list)*.2)
	degree_list_to_remove = degree_list[:cut]
	degree_list = degree_list[cut:]
	lngth_before = len(vid_to_recommend)
	print(lngth_before, 'remaining')
	for tpl in degree_list_to_remove:
		vid_to_recommend.remove(tpl[0])
		graph.remove_node(tpl[0])
	print(f"Removed {lngth_before-len(vid_to_recommend)} videos having degree of {degree_list[0][1]} or more")

	# Exclude top 80% channels (by recommendation nb)
	vids_by_channel: dict[str, list[str]] = dict()
	channel_degrees: dict[str, int] = dict()
	for tpl in degree_list:
		channel = YTDATA.videos[tpl[0]].get('cid', None)
		vids_by_channel.setdefault(channel, list()).append(tpl[0])
		channel_degrees[channel] = channel_degrees.get(channel, 0) + tpl[1]
	channel_degrees_list: list[tuple[str, int]] = [(channel, channel_degrees[channel]) for channel in channel_degrees]
	channel_degrees_list.sort(key=lambda tpl: tpl[1], reverse=True)
	cut = int(len(channel_degrees_list)*.2)
	degree_list_to_remove = channel_degrees_list[:cut]
	channel_degrees_list = channel_degrees_list[cut:]
	lngth_before = len(vid_to_recommend)
	for tpl in degree_list_to_remove:
		for vid in vids_by_channel[tpl[0]]:
			vid_to_recommend.remove(vid)
			graph.remove_node(vid)
	print(f"Removed {lngth_before-len(vid_to_recommend)} videos from channels having degree of {channel_degrees_list[0][1]} or more")

	print
	print(graph)
	print

	max_min_dist = 0
	all_recoms: list[tuple[str, str]] = list() # [(vid_to_recom, my_vid)]
	recoms: dict[str, set[str]] = dict() # vid_to_recom: {my_vid}
	my_recoms: dict[str, int] = dict() # my_vid: nb
	for other_vid in vid_to_recommend:
		for my_vid in users_vids:
			# Compute shortest distance from both videos
			dist = 0 ######

			if dist > max_min_dist:
				max_min_dist = dist
				recoms = dict()
				my_recoms = dict()
				all_recoms = list()
			if dist == max_min_dist:
				recoms.setdefault(other_vid, set()).add(my_vid)
				my_recoms[my_vid] = my_recoms.get(my_vid, 0) + 1
				all_recoms.append((other_vid, my_vid))

	all_recoms.sort(key=lambda tpl: (len(recoms[tpl[0]]), my_recoms[tpl[1]]), reverse=True)

	i = 0
	already_recommended = set()
	for rec in all_recoms:
		if rec[0] in already_recommended or rec[1] in already_recommended:
			continue
		print(f"Recommending to watch {YTDATA.videos[rec[0]]}\n\tto compare with {YTDATA.videos[rec[1]]}\n")
		i+=1
		if i > 10:
			break
		already_recommended.add(rec[0])
		already_recommended.add(rec[1])


if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) <= 3:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir> <prefuser> <languages>
	dataDir:
		Directory where the public dataset is located
		(ex: /data/input/tournesol_dataset_20001231)
	prefUser:
		User from whom get user specific statistics
		(ex: NatNgs)
	languages:
		Coma separated list of language code to accept recommendation
		(ex: fr,en)
""")
		exit(-1)

	input_dir = sys.argv[1]
	user = sys.argv[2]
	langs = sys.argv[3].split(',')

	cmp_file = ComparisonFile(input_dir)

	recom(user, cmp_file, langs)
