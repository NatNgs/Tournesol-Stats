# Imports
import subprocess
import networkx as nx
import numpy as np
import math
import os
from model.individualcriteriascores import IndividualCriteriaScoresFile
from model.comparisons import ComparisonFile, ComparisonLine
from scripts.force_directed_graph import ForceLayout
from model.youtube_api import YTData
from matplotlib import pyplot as plt
from datetime import datetime


# Constants
YTDATA_CACHE_PATH='data/YTData_cache.json.gz'
TOURNESOL_DATASET_PATH_1='data/tournesol_dataset_2023-06-05'
TOURNESOL_DATASET_PATH_2='data/tournesol_dataset_2023-06-12'
VIDEO_DIR = 'output/video/imgs'
USER = 'NatNgs'
CHANGE_LEN = 10 # More = Longer but nicer graph: Will pass to next step only once graph wasn't improved for CHANGE_LEN steps

# Setup
YTDATA = YTData()
try:
	YTDATA.load(YTDATA_CACHE_PATH)
except FileNotFoundError as e:
	pass

COMPARISONS_1 = ComparisonFile(TOURNESOL_DATASET_PATH_1)
# INDIVIDUAL_SCORES_1 = IndividualCriteriaScoresFile(TOURNESOL_DATASET_PATH_1)
COMPARISONS_2 = ComparisonFile(TOURNESOL_DATASET_PATH_2)
INDIVIDUAL_SCORES_2 = IndividualCriteriaScoresFile(TOURNESOL_DATASET_PATH_2)

# Clear imgs directory
os.system('rm -rf ' + VIDEO_DIR + '/*.png')

_link = tuple[str,str,str,int,bool]

def insert_links(sorted_links:list[_link], inserted:set[str], links:list[_link]):
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
				c = True

				if links[i] in sorted_links: # Unchanged link
					continue

				sorted_links.append(l)
				inserted.add(l[1])
				inserted.add(l[2])
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

def init_graph_data():
	links: list[_link] = list() # [(date, vid1, vid2, score[-1>1])]
	# Get all comparisons, sorted by date then by youtube ids of the contained elements (~random)
	def extract_comparisons(line: ComparisonLine):
		if line.criterion != 'largely_recommended' or line.user != USER:
			return
		links.append((line.date, line.vid1, line.vid2, line.score/10.0))

	sorted_links = list()
	inserted = set()

	COMPARISONS_1.foreach(extract_comparisons)
	links.sort()
	first = links.pop(0)
	sorted_links.append(first)
	inserted.add(first[1])
	inserted.add(first[2])
	insert_links(sorted_links, inserted, links)

	init_links = len(sorted_links)

	links.clear()
	COMPARISONS_2.foreach(extract_comparisons)
	links.sort()
	insert_links(sorted_links, inserted, links)

	cmps_to_animate = len(sorted_links) - init_links # Will draw the last x comparisons only; previous one will only be computed

	return sorted_links, cmps_to_animate

links,LAST_CMPS_TO_DRAW = init_graph_data()
G = nx.Graph()

fig,ax = plt.subplots(1,1)
pos = None
scores = INDIVIDUAL_SCORES_2.get_scores(criterion='largely_recommended', users=[USER])[USER]

begin = datetime.now()
eta_drawing = 0
eta_iterating = 0

def prettytime(d:float):
	sec = int(math.ceil(d))
	min = int(sec/60)
	hrs = int(min/60)
	if hrs > 0:
		return f"{hrs}h{min%60:02d}m"
	return f"{min:02d}m{sec%60:02d}s"

def score_to_color(score):
	# score: between -100 & +100
	r = 255
	g = 255
	if score<=0:
		g = int((1+score/100.0)*255)
	else:
		r = int((1-score/100.0)*255)

	return f'#{r:02X}{g:02X}00'
scores_color = {
	vid: score_to_color(scores[vid]['largely_recommended'][0])
	for vid in scores
}

def draw(highlight:_link, pos):
	global fnb
	ax.clear()
	ax.axis('off')

	# Edges
	for (vid1,vid2,data) in G.edges.data():
		curr_dist = np.linalg.norm((pos[vid1][0]-pos[vid2][0], pos[vid1][1]-pos[vid2][1]))
		opt_dist = data['length']
		red = int((curr_dist - opt_dist)*2)
		blue = 0
		if red < 0:
			blue = -red
			red = 0
		if red > 9:
			red = 9

		width = 2 if highlight and ((vid1 == highlight[1] and vid2 == highlight[2]) or (vid1 == highlight[2] and vid2 == highlight[1])) else 1

		ax.plot([pos[vid1][0],pos[vid2][0]], [pos[vid1][1],pos[vid2][1]], color=f"#{red}0{blue}", linewidth=width, zorder=1)

	# Nodes
	xx = []
	yy = []
	cc = []
	ss = []
	for p in pos:
		xx.append(pos[p][0])
		yy.append(pos[p][1])
		cc.append(scores_color[p])
		ss.append((len(G[p])+1)*2)
	ax.scatter(xx, yy, s=ss, c=cc, zorder=2)

	v = max(-min(xx), -min(yy), max(xx), max(yy)) * 1.01
	ax.set_xlim([-v, v])
	ax.set_ylim([-v, v])

	fnb += 1
	fig.savefig(f'{VIDEO_DIR}/frame-{fnb:06d}.png',bbox_inches='tight')

fnb = 0
lls = len(links)
LAYOUT = ForceLayout(G)
for il,l in enumerate(links):
	skip = False
	if G.has_node(l[1]) and G.has_node(l[2]):
		skip = True

	# Add a new edge
	G.add_edge(l[1], l[2], score=l[3], length=l[3]**2+0.1, date=l[0])
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

	LAYOUT.update_graph(edge_lengths='length', pos=pos)
	while change.pop(0) > min(change):
		LAYOUT.iterate3(attraction_factor=0.002, repulsion_factor=0.2, inertia_factor=0.5, repulse_upper_bound=2, iterations=10)
		change.append(LAYOUT.get_lastiteration_movement())
		drawn = lls - il < LAST_CMPS_TO_DRAW
		if drawn:
			draw(l, LAYOUT.get_pos())

		n2=datetime.now()
		spent = (n2-begin).total_seconds()
		eta = spent*(1 + 0 if not drawn else il - LAST_CMPS_TO_DRAW)/(LAST_CMPS_TO_DRAW+25*10)
		print(f"Cmp {il+1}/{lls} - {fnb:06d} {prettytime(math.ceil(fnb/24))} - ETA {prettytime(spent)}/{prettytime(eta)} ({prettytime(eta-spent)} remaining) - chg={change[-1]:0.3f}   ", end=' \r', flush=True)

for i in range(25*10):
	LAYOUT.iterate3(attraction_factor=0.002, repulsion_factor=0.2, inertia_factor=0.5*(1-i/(25*10)), repulse_upper_bound=2+i/(25*10), iterations=10)
	change.append(LAYOUT.get_lastiteration_movement())
	draw(None, LAYOUT.get_pos())

	n2=datetime.now()
	spent = (n2-begin).total_seconds()
	eta = spent/(LAST_CMPS_TO_DRAW + i)*(LAST_CMPS_TO_DRAW+25*10)
	print(f"Cmp {lls}/{lls} - {fnb:06d} {prettytime(math.ceil(fnb/24))} - ETA {prettytime(spent)}/{prettytime(eta)} (Finalizing...) - chg={change[-1]:0.3f}      ", end=' \r', flush=True)

plt.close(fig)
print('\n')

video_filename = f"output/video/{USER}.mp4"
os.remove(video_filename)
subprocess.call([
	'ffmpeg',
	'-framerate', '25',
	'-i', 'output/video/imgs/frame-%06d.png',
	'-vcodec', 'libx265',
	'-crf', '25',
	video_filename
])
