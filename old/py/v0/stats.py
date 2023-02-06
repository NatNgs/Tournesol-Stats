import sys
import time

def main():
	# Read input file
	datafolder = sys.argv[1]
	filterUser = sys.argv[2] if len(sys.argv) > 2 else None

	data = read_comparisons_file(datafolder + '/comparisons.csv')
	find_links_between_videos(data, user_vids(data, filterUser))

class Comparison:
	def __init__(self, dataLine):
		s = float(dataLine[5])

		self.u = dataLine[0]
		self.vp = dataLine[2] if s < 0 else dataLine[1]
		self.vm = dataLine[1] if s < 0 else dataLine[2]
		self.c = dataLine[3]
		# self.w = float(dataLine[4])
		self.s = abs(s)

	def __str__(self):
		if(self.s == 0):
			return f"{self.u} / {self.c}: {self.vp} = {self.vm}"
		return f"{self.u} / {self.c}: {self.vp} >{self.s}> {self.vm}"

class GroupStat:
	def __init__(self, vid, dists, allVidsLength):
		self.vid = vid # Video Id
		self.links = [len(links) for links in dists]
		self.opposites = dists[len(dists)-1]
		self.avg = 1 + sum([i*self.links[i] for i in range(len(self.links))]) / (allVidsLength-1) # Average distance to elements

	def __str__(self):
		return f"'{self.vid}' (dist avg: {self.avg} {self.links})"

def read_comparisons_file(filename):
	print('Parsing file...')
	file = open(filename, 'r', encoding='utf-8')

	# Skip header
	file.readline()

	data = []
	while True:
		line = file.readline()
		if not line:
			break
		data.append(Comparison(line.strip().split(',')))

	file.close()

	print(f'Parsed {len(data)} lines\n')
	return data


def user_vids(data, user):
	if not user:
		return None

	u_vids = {}
	for line in data:
		if line.u == user:
			u_vids.add(line.vp)
			u_vids.add(line.vm)

	print(f'{user} has compared {len(u_vids)} videos')
	return u_vids

def evaluate_vid_in_group(vid1, allVidsLength, links):
	# Compute all distances >1 from vid1
	dists = [links[vid1]]
	found = set(links[vid1]) # add all direct connections (already known)
	found.add(vid1) # add self to found (we know distance to self = 0)

	# distance: 0=no video between (one connection between), 1=one video between (two connections), ...
	distance = 0
	while len(found) < allVidsLength:
		if distance + 1 not in dists:
			dists.append([])

		for vid2 in dists[distance]:
			g2 = links[vid2]
			for vid3 in g2:
				if vid3 not in found:
					found.add(vid3)
					dists[distance+1].append(vid3)

		distance = distance+1

	return GroupStat(vid1, dists, allVidsLength)

def evaluate_group(vids, links, filter_vids=None):
	# vids: [vid1, vid2, ...]
	# links: {vid1: {vid2, ...}, vid2: {vid1, ...}, ...}
	# filter_ids: [vid1, vid2, ...] (or None)
	t = time.perf_counter()
	cntLength = int(sum(map(len, links.values()))/2)
	t = time.perf_counter() - t
	print(f'Evaluating group of {len(vids)} vids & {cntLength} connections... (Took {t:0.4f}s to compute)')

	vids.sort(key=lambda x: len(links[x]), reverse=True)
	print('Max node connections (distance = 1):', len(links[vids[0]]))

	return

	if filter_vids is None:
		filter_vids = vids

	out_stats = [ ]
	allVidsLength = len(vids)
	for i in range(len(filter_vids)):
		stt = evaluate_vid_in_group(filter_vids[i], allVidsLength, links)
		out_stats.append(stt)

		# Print
		if i%10 == 0:
			print(f"{i+1}/{allVidsLength} => {stt}")

	print('\n')
	return out_stats

def group_by_link(direct_links):
	ungroupped = dict(direct_links) # {vid1: {vid2, ..}, vid2: {vid1, ..}, ...}
	keys = list(ungroupped.keys()) # {vid1, vid2, ...}

	# Finding groups
	groups = [] # [ [vid1, vid2, ...], [vid3, vid4, ...], ...]

	while ungroupped: # While not empty
		vid1 = keys.pop()
		newgroup = [vid1]
		for toRm in newgroup:
			newgroup.extend([i for i in ungroupped.pop(toRm, []) if i not in newgroup])
			if toRm in keys: keys.remove(toRm)

		# add group
		groups.append(newgroup)

	groups.sort(key=lambda x: len(x))
	return groups

def find_links_between_videos(data, filter_vids):
	print('Computing direct links...')
	t = time.perf_counter()
	direct_links = dict() # {vid1: {vid2, ..}, vid2: {vid1, ..}, ...}
	for line in data:
		if not line.vp in direct_links: direct_links[line.vp] = set()
		if not line.vm in direct_links: direct_links[line.vm] = set()
		direct_links[line.vp].add(line.vm)
		direct_links[line.vm].add(line.vp)

	cntCnts = int(sum([len(direct_links[s]) for s in direct_links])/2)
	t = time.perf_counter() - t
	print(len(direct_links), 'videos', cntCnts, f'direct links. ({t:0.3f}s)\n')

	print('Grouping Links...')
	t = time.perf_counter()
	groups = group_by_link(direct_links)
	t = time.perf_counter() - t
	print(len(groups), f'distinct unlinked groups ({t:0.3f}s)\n')

	# Evaluating biggest group
	g1 = groups.pop()
	t = time.perf_counter()
	ev = {key: {val for val in direct_links[key] if val in g1} for key in direct_links if key in g1}
	t = time.perf_counter() - t

	group_stats = evaluate_group(g1, ev, filter_vids)
	group_stats.sort(key=lambda x: x.avg)

	print('\n')
	print('Furthest nodes in biggest group:')
	ggids = [gg['v'] for gg in group_stats]
	for i in range(1, 6):
		gg = group_stats[-i]
		print(gg['v'], '=> comparedTo:', gg['d'], '/ distToMost:', gg['b'], '/ avgDist:', round(gg['a'], 2), '/ oppositeNodes: dist =', gg['l'], sorted(gg['o'], key=lambda x: ggids.index(x))[:3])

	return #######################

	print('\nNodes not attached to biggest group:')
	prt = [g for g in groups if len(g) > 2]
	if filter_vids:
		prt = [v for v in prt if v in filter_vids]
	print(', '.join(', '.join(g) for g in sorted(prt, reverse=True)) or 'none')

# Exec
if __name__ == "__main__":
	main()
