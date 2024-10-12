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
				chennel_id: "Uabcdefghijklmnopqrstuvw"
				description: "Youtube video description"
				is_unlisted: true/false
				publication_date: "2022-12-31T23:59:59Z"
			}
		},
		collective_rating: {
			tournesol_score: 12.12345678901234 (-100 to +100)
			n_comparisons: int
			n_contributors: int
			unsafe: {
				status: true/false
				reasons: [str]
			}
		},
		criteria_scores: [{
			criteria: "backfire_risk"/"better_habits"/"diversity_inclusion"/"largely_recommended"/...
			score: 12.12345678901234 (-100 to +100)
		}],
		recommendation_metadata: {
			total_score: #unknown#
		}
'''
VData=dict[str,any]

''' CData:
	{
		entity_a: "yt:kl-XuekJxR4"
		entity_b: "yt:abcdefghijk"
		cached: "2024-12-31T23:59:59Z" (timestamp)
		criteria_scores: [{
			criteria: "largely_recommended"/...
			score: 2 (-10 to +10)
			score_max: 10
			weight: 1.0
		}]
	}
'''
CData=dict[str,any]

def timestamp():
	return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec='seconds')

class TournesolAPIDelay:
	"""
	Usage:
		with TournesolAPIDelay(tournesolapi):
			# call to Tournesol API
	"""
	def __init__(self, tournesolapi:TournesolAPI):
		self.tournesolapi = tournesolapi

	def __enter__(self):
		wait=self.tournesolapi.delay-(time.time()-self.tournesolapi.last_api_call)
		if wait > 0:
			time.sleep(wait)

	def __exit__(self, type, value, traceback):
		self.tournesolapi.last_api_call = time.time()


class TournesolAPI:
	def __init__(self, jwt:str=None):
		self.last_api_call=time.time()
		self.base_url='https://api.tournesol.app/'
		self.delay=1.0 # Seconds between call to API

		self.username = None
		self.jwt = jwt
		if jwt: # Authenticate
			userdetails = self.call_get('accounts/profile')
			assert userdetails
			assert 'username' in userdetails and userdetails['username']
			self.username = userdetails['username']

		self.file = None
		self.cache:dict[str,dict[str,any]] = {
			'all/videos_cached': "2000-12-31T23:59:59", # When was all/videos refreshed for the last time ?
			'all/videos': {}, # "vid": {vdata}

			'me/comparisons': {}, # "entity_a\tentity_b": {<cdata>}
			'me/videos': {}, # "vid": {vdata} # TODO: Remove "entity":{...} and use it from 'all/videos'
		}

	def loadCache(self, cache_file:str):
		loaded = load_json_gz(cache_file)
		for k in self.cache:
			if k in loaded:
				self.cache[k] = loaded[k]
		self.file = cache_file

	def saveCache(self):
		assert self.file
		save_json_gz(self.file, self.cache)

	def _call(self, method:Callable[[str],any], path: str, body=None):
		if path[0] == '/': # Cut leading slash in path
			path = path[1:]

		with TournesolAPIDelay(self):
			response:requests.Response = method(self.base_url + path, headers={'Authorization': self.jwt} if self.jwt else None, json=body)
			response.raise_for_status() # raises HTTPError (exc.response.status_code == 4xx or 5xx)
			return response.json()

	def call_get(self, path: str):
		return self._call(requests.get, path)

	def call_post(self, path: str, body:dict[str,any]):
		return self._call(requests.post, path, body)

	def call_patch(self, path: str, body:dict[str,any]):
		return self._call(requests.patch, path, body)

	def call_put(self, path: str, body:dict[str,any]):
		return self._call(requests.put, path, body)

	def call_delete(self, path: str, body:dict[str,any]=None):
		self._call(requests.delete, path, body)

	def callTournesolMulti(self, path: str, args:str=None, start:int=0, end:int=0, fn_continue:Callable[[list[any]], bool]=None) -> list[any]:
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
		allRes:list[VData] = last_res
		print(f'{len(allRes)}/{total}', end=' ')

		while len(allRes) < total and (end <= 0 or offset < end):
			if (fn_continue is not None) and (not fn_continue(last_res)):
				break
			offset += LIMIT
			rs = self.call_get(URL + f'&offset={offset}')
			total = rs['count']
			last_res = rs['results']
			allRes += last_res
			print(f'{len(allRes)}', end=' ')
		print('.')

		return allRes

	def getAllVideos(self, useCache=True, saveCache=True) -> list[VData]:
		now_w = datetime.datetime.now(tz=datetime.timezone.utc).isocalendar() # (year, week_num (1-52), week_day (Mon=1, Sun=7))
		cached_w = datetime.datetime.fromisoformat(self.cache['all/videos_cached']).isocalendar()
		# Refresh cache if we are after the last week data was cached
		if not useCache or (
			now_w.year > cached_w.year
			or (now_w.year == cached_w.year and (now_w.week > cached_w.week or (
					now_w.week == cached_w.week and now_w.weekday < cached_w.weekday)))):
			# TODO: Only call refresh on recent videos (depending on all/videos_cached date)
			self.getVideos(saveCache=True, params={'unsafe': 'true'})
			if saveCache:
				self.cache['all/videos_cached'] = timestamp()
				self.saveCache()
		return list(self.cache['all/videos'].values())

	def getVideos(self, saveCache=True, *, params:dict[str,str]):
		def onprogress(res:list[VData]) -> bool:
			for vdata in res:
				vid = vdata['entity']['uid']
				self.cache['all/videos'][vid] = vdata
			self.saveCache()
			return True

		allRes = self.callTournesolMulti(f"polls/videos/recommendations/", "&".join([f"{k}={v}" for k,v in params.items()]), fn_continue=onprogress if saveCache else None)
		return {vdata['entity']['uid']:vdata for vdata in allRes}


	def getVData(self, vid:str, useCache=False, saveCache=True) -> VData:
		if not useCache or vid not in self.cache['me/videos']:
			self.cache['me/videos'][vid] = self.call_get(f"users/me/contributor_ratings/videos/{vid}/")
			# /polls/videos/entities/yt:CHoXZO7WFDA : same but does not contains individual_rating
			self.cache['me/videos'][vid]['cached'] = timestamp()
		if saveCache: self.saveCache()

		return self.cache['me/videos'][vid]

	def getMyRateLater(self, saveCache=True) -> list[VData]:
		allRes = self.callTournesolMulti('users/me/rate_later/videos')
		tmstp = timestamp()
		for vdata in allRes:
			vdata['cached'] = tmstp
			self.cache['me/videos'][vdata['entity']['uid']] = vdata
		if saveCache: self.saveCache()
		return allRes

	def getMyComparedVideos(self, useCache=True, saveCache=True) -> list[VData]:
		# only call tournesol for last comparisons (until "last_compared_at" is older than cache date)
		def check_need_update(res):
			last = res[-1]['entity']['uid']
			return (not useCache) or (
				last not in self.cache['me/videos']
				or get(res[-1],'2000-00-00T00:00:00Z','individual_rating','last_compared_at') > get(self.cache['me/videos'][last],'2000-00-00T00:00:00Z','individual_rating','last_compared_at')
			)
		allRes = self.callTournesolMulti('users/me/contributor_ratings/videos', 'order_by=last_compared_at', fn_continue=check_need_update)
		tmstp = timestamp()
		for vdata in allRes:
			vdata['cached'] = tmstp
			self.cache['me/videos'][vdata['entity']['uid']] = vdata
		if saveCache: self.saveCache()
		return allRes

	def getAllMyComparisons(self, useCache=True, saveCache=True) -> list[CData]:
		def fn_continue(nextRes:list[CData]):
			# Check if at least one comparison is not yet cached
			for cdata in nextRes:
				cid = '\t'.join(sorted([cdata['entity_a']['uid'], cdata['entity_b']['uid']]))
				if not cid in self.cache['me/comparisons']:
					return True
			return False

		allRes:list[CData] = self.callTournesolMulti('users/me/comparisons/videos', fn_continue=fn_continue if useCache else None)
		# {
		#	entity_a: {uid:"yt:xxxxxx", ...},
		#	entity_b: {uid:"yt:xxxxxx", ...},
		#	criteria_scores: [{criteria: "largely_recommended", score: 10, score_max: 10, weight: 1}],
		#	...
		# }

		for cdata in allRes:
			cdata['entity_a'] = cdata['entity_a']['uid']
			cdata['entity_b'] = cdata['entity_b']['uid']
			cdata['cached'] = timestamp()
			cid = '\t'.join(sorted([cdata['entity_a'], cdata['entity_b']]))
			self.cache['me/comparisons'][cid] = cdata
			vdata1 = self.getVData(cdata['entity_a'], useCache=True, saveCache=False)
			vdata2 = self.getVData(cdata['entity_b'], useCache=True, saveCache=False)
			cdata['is_public'] = get(vdata1, False, 'individual_rating', 'is_public') and get(vdata2, False, 'individual_rating', 'is_public')

		if saveCache: self.saveCache()

		# {
		#	entity_a: "yt:xxxxx",
		#	entity_b: "yt:xxxxx",
		#	cached: "2024-12-31T23:59:59Z",
		#	criteria_scores: [...],
		#	is_public: false,
		#	...
		# }
		return list(self.cache['me/comparisons'].values())

	def getMyComparisonsWith(self, vid, saveCache=False) -> list[CData]:
		allRes = self.callTournesolMulti(f"users/me/comparisons/videos/{vid}/")
		self.getVData(vid, useCache=True)
		for cdata in allRes:
			cdata['entity_a'] = cdata['entity_a']['uid']
			cdata['entity_b'] = cdata['entity_b']['uid']
			cdata['cached'] = timestamp()
			cid = '\t'.join(sorted([cdata['entity_a'], cdata['entity_b']]))
			self.cache['me/comparisons'][cid] = cdata
			self.getVData(cdata['entity_b' if vid == cdata['entity_a'] else 'entity_a'], useCache=True, saveCache=False)

		if saveCache: self.saveCache()
		# {
		#	entity_a: "yt:xxxxx",
		#	entity_b: "yt:xxxxx",
		#	cached: "2024-12-31T23:59:59Z",
		#	criteria_scores: [...],
		#	...
		# }
		return [cdata for cid,cdata in self.cache['me/comparisons'].items() if vid in cid.split('\t')]


def get(json:VData, default, *fields):
	for f in fields:
		if f in json:
			json = json[f]
			if json is None:
				return default
		else:
			return default
	return json

def get_individual_score(vdata:VData) -> float:
	arr = [s for s in get(vdata, [], 'individual_rating', 'criteria_scores') if s['criteria'] == 'largely_recommended']
	return arr[0]['score'] if arr else None

def pretty_print_vdata(vdata: VData) -> str:
	if not 'entity' in vdata:
		return '[???]'

	vid = vdata['entity']['uid']

	score = None
	if 'collective_rating' in vdata and 'tournesol_score' in vdata['collective_rating']:
		score = f" {vdata['collective_rating']['tournesol_score']:.0f}🌻 ({vdata['collective_rating']['n_comparisons']}cmp/{vdata['collective_rating']['n_contributors']}usr)"

	if 'metadata' in vdata['entity'] and 'name' in vdata['entity']['metadata']:
		chn = vdata['entity']['metadata']['uploader'] or '???'
		nam = vdata['entity']['metadata']['name']
		return f"[{vid}]{'' if not score else score} {chn}: {nam}"

	return f"[{vid}]{'' if not score else score}"
