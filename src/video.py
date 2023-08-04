# Imports
import subprocess
import networkx as nx
import numpy as np
import math
from model.individualcriteriascores import IndividualCriteriaScoresFile
from model.comparisons import ComparisonFile, ComparisonLine
from scripts.force_directed_graph import ForceLayout
from model.youtube_api import YTData
from matplotlib import pyplot as plt
from datetime import datetime

# Constants
YTDATA_CACHE_PATH='data/YTData_cache.json'
TOURNESOL_DATASET_PATH='data/tournesol_dataset_2023-07-31'

YTDATA = YTData()
try:
	YTDATA.load(YTDATA_CACHE_PATH)
except FileNotFoundError as e:
	pass

COMPARISONS = ComparisonFile(TOURNESOL_DATASET_PATH)
INDIVIDUAL_SCORES = IndividualCriteriaScoresFile(TOURNESOL_DATASET_PATH)

USER = 'NatNgs'

_link = tuple[str,str,str,int]

def init_graph_data():
	links: list[_link] = list() # [(date, vid1, vid2, score[-1>1])]
	# Get all comparisons, sorted by date then by youtube ids of the contained elements (~random)
	def extract_comparisons(line: ComparisonLine):
		if line.criterion != 'largely_recommended' or line.user != USER:
			return
		links.append((line.date, line.vid1, line.vid2, line.score/10.0))
	COMPARISONS.foreach(extract_comparisons)
	links.sort()

	first = links.pop(0)
	sorted_links = [first]
	inserted = {first[1], first[2]}
	c = True
	while c:
		c = False

		# Find links between already added nodes
		i=0
		while i < len(links):
			if links[i][0] != sorted_links[-1][0]: # Date change, skip
				break
			if links[i][1] in inserted and links[i][2] in inserted:
				l = links.pop(i)
				sorted_links.append(l)
				inserted.add(l[1])
				inserted.add(l[2])
				c = True
			else:
				i+=1

		if c:
			continue

		for i in range(len(links)):
			if links[i][1] in inserted or links[i][2] in inserted:
				l = links.pop(i)
				sorted_links.append(l)
				inserted.add(l[1])
				inserted.add(l[2])
				c = True
				break

	return sorted_links

links = init_graph_data()
G = nx.Graph()

VIDEO_DIR = 'data/output/video/imgs'
CHANGE_LEN = 3
fig,ax = plt.subplots(1,1)
pos = None
scores = INDIVIDUAL_SCORES.get_scores(criterion='largely_recommended', users=[USER])[USER]
begin = datetime.now()


def prettytime(d:float):
	sec = int(math.ceil(d))
	min = int(sec/60)
	return f"{min:01d}:{sec%60:02d}"

def mapscores_color(score):
	if score < -75:
		return '#F00'
	if score < -50:
		return '#F40'
	if score < -15:
		return '#982'
	if score < 15:
		return '#662'
	if score < 50:
		return '#482'
	if score < 75:
		return '#4A0'
	return '#0A0'

fnb = 1
def draw(highlight:_link, pos, label, il, lls):
	global fnb
	ax.clear()
	ax.axis('off')

	# Edges
	for (vid1,vid2,data) in G.edges.data():
		curr_dist = np.linalg.norm((pos[vid1][0]-pos[vid2][0], pos[vid1][1]-pos[vid2][1]))
		opt_dist = data['weight']
		red = int((curr_dist - opt_dist)*2)
		blue = 0
		if red < 0:
			blue = -red
			red = 0
		if red > 9:
			red = 9

		width = 2 if (vid1 == highlight[1] and vid2 == highlight[2]) or (vid1 == highlight[2] and vid2 == highlight[1]) else 1

		ax.plot([pos[vid1][0],pos[vid2][0]], [pos[vid1][1],pos[vid2][1]], color=f"#{red}0{blue}", linewidth=width, zorder=1)

	# Nodes
	xx = []
	yy = []
	cc = []
	ss = []
	for p in pos:
		xx.append(pos[p][0])
		yy.append(pos[p][1])
		cc.append(mapscores_color(scores[p]['largely_recommended'][0]))
		ss.append((len(G[p])+1)*2)
	ax.scatter(xx, yy, s=ss, c=cc, zorder=2)

	v = max(-min(xx), -min(yy), max(xx), max(yy)) * 1.01
	ax.set_xlim([-v, v])
	ax.set_ylim([-v, v])

	fig.savefig(f'{VIDEO_DIR}/frame-{fnb:06d}.png',bbox_inches='tight')
	fnb += 1

	spent = (datetime.now()-begin).seconds
	eta = spent/il*lls
	print(f"{label} - {fnb:06d} {prettytime(math.ceil(fnb/24))} - ETA {prettytime(spent)}/{prettytime(eta)} ({prettytime(eta-spent)})", end='\r', flush=True)


lls = len(links)
LAYOUT = ForceLayout(G)
for il,l in enumerate(links):
	skip = False
	if G.has_node(l[1]) and G.has_node(l[2]):
		skip = True

	# Add a new edge
	G.add_edge(l[1], l[2], score=l[3], weight=abs(l[3])+0.1, date=l[0])
	if pos == None:
		pos = {l[1]:(-1,l[3]), l[2]:(1,-l[3])}
		continue

	if not l[1] in pos:
		pos[l[1]] = (pos[l[2]][0]+(1-abs(l[3])), pos[l[2]][1]+l[3])
	elif not l[2] in pos:
		pos[l[2]] = (pos[l[1]][0]-(1-abs(l[3])), pos[l[1]][1]-l[3])
	# pos = nx.spring_layout(G, pos=pos, iterations=5) # Location of points {id:(x,y)}
	change=[999]*CHANGE_LEN
	change[0] += 1

	LAYOUT.update_graph(weight='weight', pos=pos)
	while change.pop(0) > min(change):
		change.append(LAYOUT.iterate2(attraction_factor=0.01, repulsion_factor=0.2, inertia_factor=0.5, repulse_upper_bound=3))
		pos = LAYOUT.get_pos()

		draw(l, pos, f"Cmp {il+1}/{lls}", il, 2*lls)

for i in range(lls):
	LAYOUT.iterate2(attraction_factor=0.01, repulsion_factor=(lls-i)/(5*lls), inertia_factor=0.8, repulse_upper_bound=i+1)
	pos = LAYOUT.get_pos()
	draw(l, pos, f"Finalizing {i+1}/{lls}", lls+i+1, 2*lls)

plt.close(fig)
print('\n')


subprocess.call([
	'ffmpeg',
	'-framerate', '24',
	'-i', 'data/output/video/imgs/frame-%04d.png',
	f"data/output/video/{USER}.mp4"
])
