from __future__ import annotations
import time
import datetime
import requests
from typing import Callable
from utils.save import load_json_gz, save_json_gz

# Type
'''	VData:
		entity: {
			uid: "yt:kl-XuekJxR4"
			type:"video"
			metadata: {
				name: "Why Continents Are High"
				uploader: "MinuteEarth"
				tags:["tag1", "tag2", ...]
				views: int
				source: "youtube"
				duration: int (seconds)
				language: "en"
				video_id: "kl-XuekJxR4"
				channel_id: "Uabcdefghijklmnopqrstuvw"
				description: "Youtube video description"
				is_unlisted: True/False
				publication_date: "2022-12-31T23:59:59Z"
			}
		},
		collective_rating: {
			tournesol_score: 12.12345678901234 (-100 to +100)
			n_comparisons: int
			n_contributors: int
			unsafe: {
				status: True/False
				reasons: [str]
			}
		},
		'individual_rating': {
			is_public: True/False,
			n_comparisons: int,
			last_compared_at: "2020-12-31T23:59:59.999999Z"
			criteria_scores: [{
				criteria: "backfire_risk"/"better_habits"/"diversity_inclusion"/"largely_recommended"/...
				score: 12.12345678901234 (-100 to +100)
			}],
		}
		recommendation_metadata: {
			total_score: #unknown#
		}

		++++++++++++++++++++++++
		+++ ADDED PROPERTIES +++

		cached: "2020-12-31T23:59:59Z"
'''
VData=dict[str,any]

''' CData:
	{
		entity_a: "yt:kl-XuekJxR4"
		entity_b: "yt:abcdefghijk"
		criteria_scores: [{
			criteria: "largely_recommended"/...
			score: 2 (-10 to +10)
			score_max: 10
			weight: 1.0
		}]

		++++++++++++++++++++++++
		+++ ADDED PROPERTIES +++

		is_public: true/false
		cached: "2020-12-31T23:59:59Z"
	}
'''
CData=dict[str,any]

def timestamp() -> str:
	return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec='seconds')

class TournesolAPIDelay:
	"""
	Usage:
		with TournesolAPIDelay(tournesolapi):
			# call to Tournesol API
	"""
	def __init__(self, tournesolapi: TournesolAPI):
		self.tournesolapi = tournesolapi

	def __enter__(self):
		wait=self.tournesolapi.delay-(time.time()-self.tournesolapi.last_api_call)
		if wait > 0:
			time.sleep(wait)

	def __exit__(self, type, value, traceback):
		self.tournesolapi.last_api_call = time.time()


class TournesolAPI:
	def __init__(self, jwt: str=None, proxy: str=None):
		self.last_api_call=time.time()
		self.base_url='https://api.tournesol.app/'
		self.delay=1.0 # Seconds between call to API
		self.proxy = proxy

		self.username = None

		self.jwt = None
		if jwt: # Authenticate
			self.jwt = jwt.strip()
			if not self.jwt.startswith('Bearer '):
				self.jwt = 'Bearer ' + self.jwt

			userdetails = self.call_get('accounts/profile')
			assert userdetails
			assert 'username' in userdetails and userdetails['username']
			self.username = userdetails['username']

		self.file = None
		self.cache:dict[str,dict[str,any]] = {
			'all/videos_cached': "2000-12-31T23:59:59", # When full all/videos was refreshed for the last time ?
			'all/videos': {}, # "vid": vdata

			'me/videos': [], # vid
			'me/comparisons': {}, # "entity_a\tentity_b": cdata
		}


	#####################
	## CACHE MANAGMENT ##

	def loadCache(self, cache_file: str):
		loaded = load_json_gz(cache_file)
		for k in self.cache:
			if k in loaded:
				self.cache[k] = loaded[k]
		self.file = cache_file

	def saveCache(self):
		assert self.file
		save_json_gz(self.file, self.cache)

	def _cache_vdata(self, vdata: VData, time: str) -> VData:
		vid = vdata['entity']['uid']
		vdata['cached'] = time
		if vid in self.cache['all/videos']:
			# Merge with cached properties
			for part in self.cache['all/videos'][vid]:
				if part not in vdata:
					vdata[part] = self.cache['all/videos'][vid][part]
		self.cache['all/videos'][vid] = vdata
		return vdata


	################
	##  API CALLS ##

	def _call(self, method: Callable[[str],any], path: str, body=None):
		if path[0] == '/': # Cut leading slash in path
			path = path[1:]

		with TournesolAPIDelay(self):
			proxies = {
				'http': self.proxy,
				'https': self.proxy,
			} if self.proxy is not None else None

			response: requests.Response = method(self.base_url + path,
				headers={'Authorization': self.jwt} if self.jwt else None,
				json=body,
				timeout=(5,10),
				proxies=proxies,
			)
			response.raise_for_status() # raises HTTPError (exc.response.status_code == 4xx or 5xx)
			if not response.content:
				return None
			return response.json()

	def call_get(self, path: str):
		return self._call(requests.get, path)
	def call_post(self, path: str, body: dict[str,any]):
		return self._call(requests.post, path, body)
	def call_patch(self, path: str, body: dict[str,any]):
		return self._call(requests.patch, path, body)
	def call_put(self, path: str, body: dict[str,any]):
		return self._call(requests.put, path, body)
	def call_delete(self, path: str, body: dict[str,any]=None):
		self._call(requests.delete, path, body)

	def callTournesolMulti(self, path: str, args: str=None, start: int=0, end: int=0, fn_continue: Callable[[list[any]], bool]=None) -> list[any]:
		LIMIT=1000
		URL=f'{path}?limit={LIMIT}' + (('&' + args) if args else '')
		offset=start

		print(f"Calling TournesolAPI {path}...", end=' ')
		rs = self.call_get(URL + f'&offset={offset}')
		if not 'count' in rs or not 'results' in rs:
			print('##### ERROR #####')
			raise Exception(URL, rs)

		total = rs['count']
		last_res = rs['results']
		allRes: list[VData] = last_res
		print(f'{len(allRes)}/{total}', end=' ')

		if fn_continue is None or fn_continue(last_res):
			while len(allRes) < total and (end <= 0 or offset < end):
				offset += LIMIT
				rs = self.call_get(URL + f'&offset={offset}')
				total = rs['count']
				last_res = rs['results']
				allRes += last_res
				print(f'{len(allRes)}', end=' ')
				if (fn_continue is not None) and (not fn_continue(last_res)):
					break
		print('.')

		return allRes


	###########
	## VDATA ##

	def getVideosCount(self, *, params: dict[str,str]) -> int:
		# Do like getVideos but with limit = 1, and return response.count instead of response.results
		URL = "polls/videos/recommendations/?limit=1"
		if params:
			URL += "&" + "&".join([f"{k}={v}" for k,v in params.items()])
		return self.call_get(URL)['count']

	def getVideos(self, saveCache=True, *, params: dict[str,str]) -> dict[str,VData]:
		def onprogress(res: list[VData]) -> bool:
			t = timestamp()
			for vdata in res:
				self._cache_vdata(vdata, t)
			self.saveCache()
			return True

		allRes = self.callTournesolMulti(
			path=f"polls/videos/recommendations/",
			args="&".join([f"{k}={v}" for k,v in params.items()]) if params else None,
			fn_continue=onprogress if saveCache else None
		)
		return {vdata['entity']['uid']:vdata for vdata in allRes}

	def getAllVideos(self, onlyCache=False, useCache=True, saveCache=True) -> list[VData]:
		if not onlyCache:
			now_w = datetime.datetime.now(tz=datetime.timezone.utc).isocalendar() # (year, week_num (1-52), week_day (Mon=1, Sun=7))
			cached_w = datetime.datetime.fromisoformat(self.cache['all/videos_cached']).isocalendar()
			# Refresh cache if we are after the last week data was cached
			if not useCache or (
				now_w.year > cached_w.year
				or (now_w.year == cached_w.year and (now_w.week > cached_w.week or (
						now_w.week == cached_w.week and now_w.weekday < cached_w.weekday)))):
				self.getVideos(saveCache=True, params={'unsafe': 'true'})
				self.cache['all/videos_cached'] = timestamp()
				if saveCache: self.saveCache()
		return list(self.cache['all/videos'].values())


	def getVData(self, vid: str, useCache=False, saveCache=True) -> VData:
		if not useCache or vid not in self.cache['all/videos']:
			# Try to get individual scores, if not, get public video data only
			self._cache_vdata(self.call_get(f"users/me/contributor_ratings/videos/{vid}/") or self.call_get(f"/polls/videos/entities/{vid}"), timestamp())
			if saveCache: self.saveCache()
		return self.cache['all/videos'][vid]

	def getMyRateLater(self, saveCache=True) -> list[VData]:
		def onresult(res: list[VData]) -> bool:
			tmstp = timestamp()
			for vdata in res:
				self._cache_vdata(vdata, tmstp)
			if saveCache: self.saveCache()
			return True
		return self.callTournesolMulti('users/me/rate_later/videos', fn_continue=onresult)

	def getMyComparedVideos(self, useCache=True, saveCache=True, onlyCache=False) -> list[VData]:
		if onlyCache:
			return list(map(self.cache['all/videos'].get, self.cache['me/videos']))

		vids = set() if not useCache else set(self.cache['me/videos'])

		# only call tournesol for last comparisons (until "last_compared_at" is older than cache date)
		def check_need_update(res):
			last = res[-1]['entity']['uid']
			need_continue = ((last not in vids)
				or get(res[-1],'2000-00-00T00:00:00Z','individual_rating','last_compared_at') > get(self.cache['all/videos'][last],'2000-00-00T00:00:00Z','individual_rating','last_compared_at')
			)

			# Update new received videos data
			tmstp = timestamp()
			for vdata in res:
				self._cache_vdata(vdata, tmstp)
				vids.add(vdata['entity']['uid'])

			return need_continue
		self.callTournesolMulti('users/me/contributor_ratings/videos', 'order_by=-last_compared_at', fn_continue=check_need_update)

		self.cache['me/videos'] = sorted(vids)
		if saveCache: self.saveCache()
		return list(map(self.cache['all/videos'].get, vids))

	def getChannelVideos(self, channelTitle: str, onlyCache=False) -> dict[str, VData]:
		if not onlyCache:
			allRes = self.callTournesolMulti('/polls/videos/recommendations/',
				args=f"unsafe=true&exclude_compared_entities=false&metadata[uploader]={channelTitle}")

			tmstp = timestamp()
			return {vdata['entity']['uid']:self._cache_vdata(vdata, tmstp) for vdata in allRes}

		# From cache
		return {vdata['entity']['uid']:vdata for vdata in self.cache['all/videos'].values() if get(vdata, None, 'entity', 'metadata', 'uploader') == channelTitle}

	###########
	## CDATA ##

	def getAllMyComparisons(self, useCache=True, saveCache=True, onlyCache=False) -> list[CData]:
		if onlyCache:
			return list(self.cache['me/comparisons'].values())

		out = self.cache['me/comparisons'] if useCache else {}

		def fn_continue(nextRes: list[CData]):
			tmstp = timestamp()
			need_continue = not useCache # if useCache=False, force return True to get all data

			for cdata in nextRes:
				# cdata = {
				#	entity_a: {uid:"yt:xxxxxx", ...},
				#	entity_b: {uid:"yt:xxxxxx", ...},
				#	criteria_scores: [{criteria: "largely_recommended", score: 10, score_max: 10, weight: 1}],
				#	...
				# }
				cdata['entity_a'] = cdata['entity_a']['uid']
				cdata['entity_b'] = cdata['entity_b']['uid']
				cid = '\t'.join(sorted([cdata['entity_a'], cdata['entity_b']]))
				cdata['cached'] = tmstp
				vdata1 = self.getVData(cdata['entity_a'], useCache=True, saveCache=False)
				vdata2 = self.getVData(cdata['entity_b'], useCache=True, saveCache=False)
				cdata['is_public'] = get(vdata1, False, 'individual_rating', 'is_public') and get(vdata2, False, 'individual_rating', 'is_public')
				# cdata = {
				#	entity_a: "yt:xxxxx",
				#	entity_b: "yt:xxxxx",
				#	criteria_scores: [...],
				#	...
				#	is_public: false,
				#	cached: "2020-12-31T23:59:59Z",
				# }

				if useCache and cid not in out: need_continue = True # At least one new comparison has been found; will ask to get the next batch
				out[cid] = cdata

			return need_continue

		self.callTournesolMulti('users/me/comparisons/videos', fn_continue=fn_continue)
		if saveCache: self.saveCache()
		return list(out.values())

	def getMyComparisonsWith(self, vid, useCache=True, saveCache=False) -> list[CData]:
		# Check from cache if update is needed
		vdata1 = self.getVData(vid, useCache=True, saveCache=False)

		if useCache:
			expected_cmps = get(vdata1, 0, 'individual_rating', 'n_comparisons')
			cached_cmps = [cdata for cid,cdata in self.cache['me/comparisons'].items() if vid in cid.split('\t')]
			# All comparisons found in cache, no need to fetch API
			if expected_cmps == len(cached_cmps):
				return cached_cmps

		allRes = self.callTournesolMulti(f"users/me/comparisons/videos/{vid}/")
		tmstp = timestamp()

		for cdata in allRes:
			cdata['entity_a'] = cdata['entity_a']['uid']
			cdata['entity_b'] = cdata['entity_b']['uid']
			cdata['cached'] = tmstp
			cid = '\t'.join(sorted([cdata['entity_a'], cdata['entity_b']]))
			vdata2 = self.getVData(cdata['entity_b' if vid == cdata['entity_a'] else 'entity_a'], useCache=True, saveCache=False)
			cdata['is_public'] = get(vdata1, False, 'individual_rating', 'is_public') and get(vdata2, False, 'individual_rating', 'is_public')
			self.cache['me/comparisons'][cid] = cdata

		if saveCache: self.saveCache()
		# {
		#	entity_a: "yt:xxxxx",
		#	entity_b: "yt:xxxxx",
		#	cached: "2024-12-31T23:59:59Z",
		#	criteria_scores: [...],
		#	...
		# }
		return [cdata for cid,cdata in self.cache['me/comparisons'].items() if vid in cid.split('\t')]


#################################
##           UTILS             ##
#################################

def get(json: VData, default, *fields):
	for f in fields:
		if f in json:
			json = json[f]
			if json is None:
				return default
		else:
			return default
	return json

def get_individual_score(vdata: VData) -> float:
	arr = [s for s in get(vdata, [], 'individual_rating', 'criteria_scores') if s['criteria'] == 'largely_recommended']
	return arr[0]['score'] if arr else None

def pretty_print_vdata(vdata: VData) -> str:
	if not 'entity' in vdata:
		return '[???]'

	vid = vdata['entity']['uid']

	score = None
	if 'collective_rating' in vdata and 'tournesol_score' in vdata['collective_rating']:
		score = f" {vdata['collective_rating']['tournesol_score']:+3.0f}🌻 ({vdata['collective_rating']['n_comparisons']:3d}cmp/{vdata['collective_rating']['n_contributors']:2d}ctr)"

	if 'metadata' in vdata['entity'] and 'name' in vdata['entity']['metadata']:
		chn = vdata['entity']['metadata']['uploader'] or '???'
		nam = vdata['entity']['metadata']['name']
		return f"[{vid}]{'' if not score else score} {chn}: {nam}"

	return f"[{vid}]{'' if not score else score}"
