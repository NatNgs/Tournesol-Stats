#
# Usage:
#	python src/py/scripts/missing_contrib.py
#	or
#	python src/py/scripts/missing_contrib.py <privatebin service url>
#
# See available services here:
# https://www.chatons.org/search/by-service?service_type_target_id=127&field_alternatives_aux_services_target_id=All&field_software_target_id=All&field_is_shared_value=All&title=
#

import os
import re
import sys
import time
import datetime
from privatebin import Formatter, PrivateBin, Expiration

# Ensure script is running from Tournesol-Stats dir
_pwd = os.path.realpath('.').split(os.sep)
if 'src' in _pwd:
	while _pwd[-1] != 'src':
		_pwd.pop()
	_pwd.pop() # Go up from src dir to Tournesol-Stats
	os.chdir(os.sep.join(_pwd))
print('Running from', os.path.realpath('.'))

# Local project requirements
sys.path.append('src/py')
from dao.tournesol_api import TournesolCommonAPI, get
from model.solidago import TournesolInputFromPublicDataset



TOURNESOL = TournesolCommonAPI('./data/TournesolAPI_cache')
TOURNESOL.loadCache()

PUBLIC_DATASET = TournesolInputFromPublicDataset.download()
PASTEBIN_LAST_REQUEST = datetime.datetime.fromisoformat('2000-01-01T00:00:00')


# All tournesol videos having 1 or 2 contributors and positive score

def sanitizeMd(s:str):
	s = re.sub(r'\s+', ' ', s) # Sanitize spaces
	MD_SPECIAL_CHARS = '\\`*_{}[]()#+-.!'
	for char in MD_SPECIAL_CHARS:
		s = s.replace(char, '\\'+char)
	return s.strip()

def _getContribs(lang:str, contributors:tuple[int,int], minscore:int, maxscore:int):
	print('Extracting...')
	allRes:list = TOURNESOL.callTournesolMulti(
		'polls/videos/recommendations/',
		f'unsafe=true&metadata%5Blanguage%5D={lang}',
		fn_continue=lambda res: res[-1]['collective_rating']['tournesol_score'] >= minscore)
	allRes = [vdata for vdata in allRes if
		    get(vdata, 0, 'collective_rating', 'n_contributors') >= contributors[0]
		and get(vdata, 0, 'collective_rating', 'n_contributors') <= contributors[-1]
		and get(vdata, 0, 'collective_rating', 'tournesol_score') >= minscore
		and get(vdata, 0, 'collective_rating', 'tournesol_score') <= maxscore
	]
	allRes.sort(key=lambda vdata: (
		round(get(vdata, 0, 'collective_rating', 'tournesol_score')),
		get(vdata, 0, 'collective_rating', 'n_comparisons')
	), reverse=True)
	authors:dict[str,list] = dict()
	for vdata in allRes:
		a = get(vdata, '???', 'entity', 'metadata', 'uploader')
		authors.setdefault(a, list()).append(vdata)

	allData = []
	for vdata in allRes:
		tscore=round(get(vdata, 0, 'collective_rating', 'tournesol_score'))
		tcmps=get(vdata, 0, 'collective_rating', 'n_comparisons')
		tctrs=get(vdata, 0, 'collective_rating', 'n_contributors')
		tchannel=sanitizeMd(get(vdata, '???', 'entity', 'metadata', 'uploader'))
		tname=sanitizeMd(get(vdata, '???', 'entity', 'metadata', 'name'))
		tpubli=get(vdata, '???', 'entity', 'metadata', 'publication_date')
		tdur=get(vdata, 0, 'entity', 'metadata', 'duration')
		tminutes=f"{int(tdur/60):2d}:{tdur%60:02d}" if tdur < 3600 else f"{int(tdur/3600)}:{int((tdur%3600)/60):02d}:{tdur%60:02d}"
		turl=f"https://tournesol.app/entities/{vdata['entity']['uid']}"

		# Find the public contributors of this video from public dataset
		publicContributors = list(PUBLIC_DATASET.get_comparisons(vid=vdata['entity']['uid'])['user_id'].unique())
		# Convert publicContributors (list of user_id) to public_username using PUBLIC_DATASET.users
		publicContributors = list(PUBLIC_DATASET.users[PUBLIC_DATASET.users.index.isin(publicContributors)]['public_username'])

		allData.append((tscore, tctrs, tcmps, tpubli, tminutes, tchannel, tname, turl, publicContributors))

	return sorted(allData, reverse=True)

def getContribByYear(lang:str, contributors:tuple[int,int], minscore:int, maxscore:int=20):
	allData = _getContribs(lang=lang, contributors=contributors, minscore=minscore, maxscore=maxscore)

	authors:set[str] = set()
	yearmap:dict[str,list[tuple]] = {}
	for vdata in allData:
		authors.add(vdata[5])
		yearmap.setdefault(vdata[3][0:4], []).append(vdata)

	return (len(allData), len(authors), yearmap)

def getContribByAuthor(lang:str, contributors:tuple[int,int], minscore:int, maxscore:int=20):
	allData = _getContribs(lang=lang, contributors=contributors, minscore=minscore, maxscore=maxscore)

	authors:dict[str,list[tuple]] = {}
	for vdata in allData:
		authors.setdefault(vdata[5], []).append(vdata)

	return (len(allData), len(authors), authors)

def writeFile(file:str, lines:list[str], private_bin: PrivateBin|None):
	global PASTEBIN_LAST_REQUEST
	with open(file, 'w', encoding='utf-8') as f:
		for line in lines:
			f.write(line + '\n')
	print('File written: ' + file)

	if private_bin:
		try:
			sleeptime = (PASTEBIN_LAST_REQUEST - datetime.datetime.now() + datetime.timedelta(minutes=1)).total_seconds()
			if sleeptime > 0: time.sleep(sleeptime) # Wait one minute between posts to avoid rate limit
			receipt = private_bin.create('\n'.join(lines), expiration=Expiration.ONE_YEAR, formatter=Formatter.MARKDOWN)
			print('Markdown uploaded to pastebin:', str(receipt.url).replace('********', receipt.url.passphrase))
			PASTEBIN_LAST_REQUEST = datetime.datetime.now()
		except Exception as e:
			print('WARN: Failed to upload file to PrivateBin:', e, file=sys.stderr)
	print()

def _extract_prev_data(filename:str) -> dict[str,int]:
	prev_data:dict[str,int] = {}
	try:
		with open(filename, 'r', encoding='utf-8') as f:
			for line in f:
				try:
					prev_data[re.search(r'yt:[0-9a-zA-Z_-]{11}', line).group(0)] = int(re.search(r'\((\d+) cmps /', line).group(1))
				except:
					pass # Not a valid line
	except FileNotFoundError:
		print('WARN: Previous stats file not found: ' + filename, file=sys.stderr)
		return {}
	if not prev_data:
		print('WARN: No match found in previous stats file: ' + filename, file=sys.stderr)
	return prev_data

def _make_new_old_dicts(allRes, prev_data) -> tuple[dict[str,list[tuple]], dict[str,list[tuple]], int, int]:
	new_vids:dict[str, list[tuple]] = {} # {channel: [vdata]}, with vdata only if not present in prev_data (or if tcmps different than prev_data value)
	new_cnt = 0
	old_vids:dict[str, list[tuple]] = {}
	old_cnt = 0
	for channel in sorted(allRes, key=lambda x:len(allRes[x]), reverse=True):
		new_vids[channel] = []
		old_vids[channel] = []
		for tdata in sorted(allRes[channel], reverse=True):
			(tscore, tctrs, tcmps, tdate, tminutes, tchannel, tname, turl, cntrs) = tdata

			# Add to diffs
			vid = re.search(r'yt:[0-9a-zA-Z_-]{11}', turl).group(0)
			if vid in prev_data and prev_data[vid] == tcmps:
				old_vids[channel].append(tdata)
				old_cnt += 1
			else:
				new_vids[channel].append(tdata)
				new_cnt += 1
		# Remove empty channels from diffs
		if not new_vids[channel]:
			new_vids.pop(channel)
		if not old_vids[channel]:
			old_vids.pop(channel)
	return (new_vids,old_vids,new_cnt,old_cnt)

#### ------------------

def build_markdown(curr_contribs, prev_data, lang:dict[str,str]):
	dt = datetime.datetime.now()

	# Extracting from API
	(cnt_vids,cnt_authors,allRes) = curr_contribs

	# Preparing data
	new_vids,old_vids,new_cnt,old_cnt = _make_new_old_dicts(allRes, prev_data)

	def apply_lang(tdata, lang, with_channel_name:bool=False):
		(tscore, tctrs, tcmps, tdate, tminutes, tchannel, tname, turl, cntrs) = tdata
		_cntrs = '' if not cntrs else lang['compared_by__sep'] + sanitizeMd(cntrs[0])
		return (lang['vdata']
				.replace(r'{tscore}', f'{tscore:3.0f}')
				.replace(r'{tcntrs}', str(tctrs))
				.replace(r'{tcmps}', str(tcmps))
				.replace(r'{vlen}', str(tminutes))
				.replace(r'{lib_user}', lang['lib_user_single'] if tctrs == 1 else lang['lib_user_multi'])
			+ (f' **{tchannel}**:' if with_channel_name else '')
			+ (f' [{tname}]({turl})')
			+ _cntrs
		)

	# Append header
	markdown = []
	markdown.append(lang['title'])
	markdown.append(lang['header'].replace(r'{date}', str(dt)[:16]).replace(r'{cnt_vids}', str(cnt_vids)).replace(r'{cnt_channels}', str(cnt_authors)))

	markdown.append('---\n\n')

	# Write the new_vids
	markdown.append(lang['new__title'])
	markdown.append(lang['new__desc'].replace(r'{new__vids}', str(new_cnt)).replace(r'{new__channels}', str(len(new_vids))))
	for channel in sorted(new_vids, key=lambda x:len(new_vids[x]), reverse=True):
		if len(new_vids[channel]) > 1:
			markdown.append(f'\n### {channel}')
			for tdata in new_vids[channel]:
				markdown.append(apply_lang(tdata, lang))
	others = [new_vids[channel][0] for channel in new_vids if len(new_vids[channel]) == 1]
	if len(others) > 0 and sum(1 for channel in new_vids if len(new_vids[channel]) > 1) > 0: markdown.append(f"\n### _{lang['other_category']}_")
	for tdata in sorted(others, reverse=True):
		markdown.append(apply_lang(tdata, lang, with_channel_name=True))

	markdown.append('\n---\n\n')

	# Write the old_vids
	markdown.append(lang['old__title'])
	markdown.append(lang['old__desc'].replace(r'{old__vids}', str(old_cnt)).replace(r'{old__channels}', str(len(old_vids))))
	for channel in sorted(old_vids, key=lambda x:len(old_vids[x]), reverse=True):
		if len(old_vids[channel]) > 1:
			markdown.append(f'\n### {channel}')
			for tdata in old_vids[channel]:
				markdown.append(apply_lang(tdata, lang))
	others = [old_vids[channel][0] for channel in old_vids if len(old_vids[channel]) == 1]
	if len(others) > 0 and sum(1 for channel in old_vids if len(old_vids[channel]) > 1) > 0: markdown.append(f"\n### _{lang['other_category']}_")
	for tdata in sorted(others, reverse=True):
		markdown.append(apply_lang(tdata, lang, with_channel_name=True))

	return markdown

#### ------------------

LANGS = {
	'fr': {
		'new__title': '## Vidéos récemment comparées\n',
		'new__desc': '{new__vids} vidéos récemment comparées par {new__channels} chaînes',
		'old__title': '## Vidéos non récemment comparées\n',
		'old__desc': '{old__vids} vidéos non-récemment comparées par {old__channels} chaînes',
		'vdata': '- {tscore}🌻 ({tcmps} cmps / {tcntrs} {lib_user}) \\[{vlen}\\]',
		'compared_by__sep': ' ~ comparé par ',
		'lib_user_single': 'cntr',
		'lib_user_multi': 'cntrs',
		'other_category': 'Autres',
	},
	'en': {
		'new__title': '## Recently compared\n',
		'new__desc': '{new__vids} recently compared videos by {new__channels} channels\n',
		'old__title': '## Not recently compared\n',
		'old__desc' : '{old__vids} non-recently compared videos by {old__channels} channels\n',
		'vdata': '- {tscore}🌻 ({tcmps} cmps / {tcntrs} {lib_user}) \\[{vlen}\\]',
		'compared_by__sep': ' ~ compared by ',
		'lib_user_single': 'user',
		'lib_user_multi': 'users',
		'other_category': 'Others',
	},
}

def _en_1_contrib(week: str, out_dir: str, prev_dir: str, private_bin):
	lang = {k:v for k,v in LANGS['en'].items()}
	lang['title'] = '# Single contributors on Tournesol\n'
	lang['header'] = (
		'Here are extracted all the videos in English that have been compared by a single contributor on [Tournesol](https://tournesol.app).\n\n'
		'Extraction date: {date}\n\n'
		'Found {cnt_vids} videos by {cnt_channels} channels\n'
	)

	markdown = build_markdown(
		getContribByAuthor('en', contributors=(1, 1), minscore=5),
		_extract_prev_data(f'{prev_dir}/en_{prev_dir.split('/')[-1]}_contribs-1.md'),
		lang
	)
	writeFile(f'{out_dir}/en_{week}_contribs-1.md', markdown, private_bin)

def _en_2_contribs(week:str, out_dir:str, prev_dir:str, private_bin):
	lang = {k:v for k,v in LANGS['en'].items()}
	lang['title'] = '# Tournesol missing contributors list\n'
	lang['header'] = (
		'Here are extracted all the videos in English that may go publically recommended with only one more contributor on [Tournesol](https://tournesol.app).\n\n'
		'Extraction date: {date}\n\n'
		'Found {cnt_vids} videos by {cnt_channels} channels\n'
	)

	markdown = build_markdown(
		getContribByAuthor('en', contributors=(2, 2), minscore=15),
		_extract_prev_data(f'{prev_dir}/en_{prev_dir.split('/')[-1]}_contribs-2.md'),
		lang
	)
	writeFile(f'{out_dir}/en_{week}_contribs-2.md', markdown, private_bin)

def _en_35_contribs(week: str, out_dir: str, prev_dir: str, private_bin):
	lang = {k:v for k,v in LANGS['en'].items()}
	lang['title'] = '# Tournesol few contributors list\n'
	lang['header'] = (
		'Here are extracted all the videos in English that have a score near 20, with 3 to 5 contributors on [Tournesol](https://tournesol.app).\n\n'
		'Extraction date: {date}\n\n'
		'Found {cnt_vids} videos by {cnt_channels} channels\n'
	)

	markdown = build_markdown(
		getContribByAuthor('en', contributors=(3, 5), minscore=18, maxscore=22),
		_extract_prev_data(f'{prev_dir}/en_{prev_dir.split('/')[-1]}_contribs-35.md'),
		lang
	)
	writeFile(f'{out_dir}/en_{week}_contribs-35.md', markdown, private_bin)


def _fr_1_contrib(week: str, out_dir: str, prev_dir: str, private_bin):
	lang = {k:v for k,v in LANGS['fr'].items()}
	lang['title'] = '# Vidéos faiblement comparées\n'
	lang['header'] = (
		"Ci-dessous sont extraites l'ensemble des vidéos Francophones auquelles il manque plusieurs contributeurs pour pouvoir être recommandées sur [Tournesol](https://tournesol.app).\n\n"
		"Date de l'extraction: {date}\n\n"
		'{cnt_vids} vidéos trouvées par {cnt_channels} chaines différentes\n'
	)

	markdown = build_markdown(
		getContribByAuthor('fr', contributors=(1, 1), minscore=6),
		_extract_prev_data(f'{prev_dir}/fr_{prev_dir.split('/')[-1]}_contribs-1.md'),
		lang
	)
	writeFile(f'{out_dir}/fr_{week}_contribs-1.md', markdown, private_bin)

def _fr_2_contribs(week: str, out_dir: str, prev_dir: str, private_bin):
	lang = {k:v for k,v in LANGS['fr'].items()}
	lang['title'] = '# Vidéos manquants de contributeurs\n'
	lang['header'] = (
		"Ci-dessous sont extraites l'ensemble des vidéos Francophones qui pourraient être publiquement recommandées avec un seul nouveau contributeur sur [Tournesol](https://tournesol.app).\n\n"
		"Date de l'extraction: {date}\n\n"
		'{cnt_vids} videos trouvées par {cnt_channels} chaines différentes\n'
	)

	markdown = build_markdown(
		getContribByAuthor('fr', contributors=(2, 2), minscore=15),
		_extract_prev_data(f'{prev_dir}/fr_{prev_dir.split('/')[-1]}_contribs-2.md'),
		lang
	)
	writeFile(f'{out_dir}/fr_{week}_contribs-2.md', markdown, private_bin)

def _fr_35_contrib(week: str, out_dir: str, prev_dir: str, private_bin):
	lang = {k:v for k,v in LANGS['fr'].items()}
	lang['title'] = '# Vidéos faiblement comparées\n'
	lang['header'] = (
		"Ci-dessous sont extraites l'ensemble des vidéos Francophones ayant un score proche de 20, et par entre 3 et 5 contributeurs sur [Tournesol](https://tournesol.app).\n\n"
		"Date de l'extraction: {date}\n\n"
		'{cnt_vids} videos trouvées par {cnt_channels} chaines diferentes\n'
	)

	markdown = build_markdown(
		getContribByAuthor('fr', contributors=(3, 5), minscore=18, maxscore=22),
		_extract_prev_data(f'{prev_dir}/fr_{prev_dir.split('/')[-1]}_contribs-35.md'),
		lang
	)
	writeFile(f'{out_dir}/fr_{week}_contribs-35.md', markdown, private_bin)

#### -----------------

## RUN

if __name__ == '__main__':
	# Fetch arguments, if there is an argument, take it as private bin url
	private_bin = None
	if len(sys.argv) > 1:
		private_bin = PrivateBin(sys.argv[1])

	# Week is the date of the nearest monday in the past (today if today is monday), to ISO format yyyy-mm-dd
	now = datetime.datetime.now(tz=datetime.timezone.utc)
	week = (now - datetime.timedelta(days=now.weekday())).strftime('%Y-%m-%d')

	parent_out_dir = 'output/missing-contribs'
	out_dir = f'{parent_out_dir}/{week}'

	prev_week = max(d for d in os.listdir(parent_out_dir) if d < week)
	prev_dir = f'{parent_out_dir}/{prev_week}'

	# Prepare output
	os.makedirs(out_dir, exist_ok=True)

	# Run !
	_en_35_contribs(week, out_dir, prev_dir, private_bin)
	_en_2_contribs(week, out_dir, prev_dir, private_bin)
	_en_1_contrib(week, out_dir, prev_dir, private_bin)

	_fr_35_contrib(week, out_dir, prev_dir, private_bin)
	_fr_2_contribs(week, out_dir, prev_dir, private_bin)
	_fr_1_contrib(week, out_dir, prev_dir, private_bin) # The largest at the end

	TOURNESOL.saveCache()
