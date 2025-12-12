from __future__ import annotations
import os
import time
import datetime
import requests
from typing import Callable
from utils.save import load_json_gz, save_json_gz
from requests.adapters import HTTPAdapter, Retry

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
				publication_0date: "2022-12-31T23:59:59Z"
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
	def __init__(self, tournesolapi: TournesolCommonAPI):
		self.tournesolapi = tournesolapi

	def __enter__(self):
		wait=self.tournesolapi.delay-(time.time()-self.tournesolapi.last_api_call)
		if wait > 0:
			time.sleep(wait)

	def __exit__(self, type, value, traceback):
		self.tournesolapi.last_api_call = time.time()


class TournesolCommonAPI:
	def __init__(self, cache_dir:str, proxy:str|None=None):
		self.last_api_call=time.time()
		self.protocol='https'
		self.base_url=f"{self.protocol}://api.tournesol.app/" # need to end with '/'
		self.delay=1.0 # Seconds between call to API
		self.proxy = proxy

		self.cache_file = os.path.join(cache_dir, 'common.json.gz')
		self.videos:dict[str,VData] = {} # vid: vdata common part

	#####################
	## CACHE MANAGMENT ##

	def loadCache(self):
		loaded = load_json_gz(self.cache_file)
		assert 'common_vdata' in loaded, 'File content structure is not as expected'
		self.videos = loaded['common_vdata']

	def saveCache(self) -> str:
		print('§', end=' ', flush=True)
		return save_json_gz(self.cache_file, {
			'common_vdata': self.videos
		})

	def _get_from_cache(self, vid:str) -> VData:
		return self.videos[vid]

	def _cache_vdata(self, vdata:VData, time:str) -> VData:
		vid = vdata['entity']['uid']

		# Separate common and user-specific data
		common_part = {}
		for key,value in vdata.items():
			if key in {'entity', 'collective_rating'}:
				common_part[key] = value

		# Update cache
		if common_part:
			common_part['cached'] = time
			self.videos[vid] = common_part
		return self._get_from_cache(vid)

	################
	##  API CALLS ##

	def _call(self, method:str, path:str, body=None, jwt:str|None=None):
		if path[0] == '/': # Cut leading slash in path
			path = path[1:]

		response: requests.Response = None
		retry=Retry(
			connect=5,
			redirect=5,
			status=3,
			read=2,
			other=2,
			backoff_factor=self.delay,
			allowed_methods=None, # Allow retry on every method
			status_forcelist=[429, 500, 502, 503, 504],
		)
		with TournesolAPIDelay(self):
			s = requests.Session()
			s.mount(self.protocol + '://', HTTPAdapter(max_retries=retry))
			response: requests.Response = getattr(s, method)(self.base_url + path,
				headers={'Authorization': jwt} if jwt else None,
				json=body,
				proxies=
					{self.protocol: self.proxy} if self.proxy is not None
					else None,
				timeout=(5,10)
			)
		response.raise_for_status() # raises HTTPError (exc.response.status_code == 4xx or 5xx)
		if not response.content:
			return None
		return response.json()

	def call_get(self, path:str, jwt:str|None=None):
		return self._call('get', path, jwt=jwt)
	def call_post(self, path:str, body:dict[str,any], jwt:str|None=None):
		return self._call('post', path, body, jwt=jwt)
	def call_patch(self, path:str, body:dict[str,any], jwt:str|None=None):
		return self._call('patch', path, body, jwt=jwt)
	def call_put(self, path:str, body:dict[str,any], jwt:str|None=None):
		return self._call('put', path, body, jwt=jwt)
	def call_delete(self, path:str, body:dict[str,any]=None, jwt:str|None=None):
		self._call('delete', path, body, jwt=jwt)
	def call_options(self, path:str, body:dict[str,any]=None, jwt:str|None=None):
		self._call('options', path, body, jwt=jwt)

	def callTournesolMulti(self, path:str, args:str=None, start:int=0, end:int=0, fn_continue:Callable[[list[any]],bool]=None, jwt:str|None=None) -> list[any]:
		LIMIT=1000
		URL=f'{path}?limit={LIMIT}' + (('&' + args) if args else '')
		offset=start

		print(f"[TNSL API] {path}...", end=' ')
		rs = self.call_get(URL + f'&offset={offset}', jwt=jwt)
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
				rs = self.call_get(URL + f'&offset={offset}', jwt=jwt)
				total = rs['count']
				last_res = rs['results']
				allRes += last_res
				print(f'{len(allRes)}', end=' ')
				if (fn_continue is not None) and (not fn_continue(last_res)):
					break
		print('.')

		return allRes

	#############
	##  VDATA  ##

	def getVData(self, vid:str, useCache=False, saveCache=False) -> VData:
		if vid[:3] != 'yt:':
			vid = 'yt:' + vid
		if len(vid) != 14:
			raise Exception('Wrong video id: ' + vid)

		if not useCache or vid not in self.videos:
			try:
				got = self.call_get(f"/polls/videos/entities/{vid}")
			except Exception:
				raise Exception(f"Could not fetch video {vid}")
			self._cache_vdata(got, timestamp())
			if saveCache: self.saveCache()
		return self._get_from_cache(vid)


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

	def prettyPrintVData(self, vid: str|VData, useCache=True, saveCache=False) -> str:
		if isinstance(vid, str):
			return _pretty_print_vdata(self.getVData(vid, useCache=useCache, saveCache=saveCache))
		else:
			return _pretty_print_vdata(vid)

	def getChannelVideos(self, channelTitle: str, onlyCache=False) -> dict[str, VData]:
		if not onlyCache:
			allRes = self.callTournesolMulti('/polls/videos/recommendations/', args=f"unsafe=true&exclude_compared_entities=false&metadata[uploader]={channelTitle}")

			tmstp = timestamp()
			return {vdata['entity']['uid']:self._cache_vdata(vdata, tmstp) for vdata in allRes}

		# From cache
		return {vdata['entity']['uid']:vdata for vdata in self.videos.values() if get(vdata, None, 'entity', 'metadata', 'uploader') == channelTitle}


class TournesolUserAPI:
	def __init__(self, commonApi:TournesolCommonAPI, jwt:str, cache_dir:str|None=None):
		self.common = commonApi

		# Authentication
		self.username = None
		self.jwt = jwt.strip()
		if not self.jwt.startswith('Bearer '):
			self.jwt = 'Bearer ' + self.jwt

		userdetails = self.common.call_get('accounts/profile', jwt=self.jwt)
		assert userdetails
		assert 'username' in userdetails and userdetails['username']
		self.username = userdetails['username']

		# Cache
		if not cache_dir:
			cache_dir = os.path.dirname(commonApi.cache_file)
		self.cache_file = os.path.join(cache_dir, 'users', f'{self.username}.json.gz')
		self.videos:dict[str,VData] = {} # vid: vdata user part
		self.comparisons:dict[str,CData] = {} # "entity_a\tentity_b": cdata

	#####################
	## CACHE MANAGMENT ##

	def loadCache(self):
		if not self.common.videos:
			self.common.loadCache()
		loaded = load_json_gz(self.cache_file)
		assert 'videos' in loaded and 'comparisons' in loaded, 'File content structure is not as expected'
		self.videos = loaded['videos']
		self.comparisons = loaded['comparisons']

	def saveCache(self) -> str:
		self.common.saveCache()
		print('¤', end=' ', flush=True)
		return save_json_gz(self.cache_file, {
			'videos': self.videos,
			'comparisons': self.comparisons,
		})

	def _get_from_cache(self, vid:str) -> VData:
		res = self.common._get_from_cache(vid)
		if vid in self.videos:
			res.update(self.videos[vid])
		return res

	def _cache_vdata(self, vdata: VData, time: str) -> VData:
		vid = vdata['entity']['uid']
		common_part = self.common._cache_vdata(vdata, time)

		# Separate common and user-specific data
		user_part = {}
		for key,value in vdata.items():
			if key not in common_part:
				user_part[key] = value

		# Update cache
		if user_part:
			user_part['cached'] = time
			self.videos[vid] = user_part
		return self._get_from_cache(vid)

	#############
	##  VDATA  ##

	def getVData(self, vid:str, useCache=False, saveCache=False, postIfMissing=True) -> VData:
		if vid[:3] != 'yt:':
			vid = 'yt:' + vid
		if len(vid) != 14:
			raise Exception('Wrong video id: ' + vid)

		if not useCache or vid not in self.videos:
			# Try to get individual scores, if not, get public video data only
			try:
				got = self.common.call_get(f"users/me/contributor_ratings/videos/{vid}/", jwt=self.jwt)
				got = self._cache_vdata(got, timestamp())
				if saveCache: self.saveCache()
				return got
			except Exception:
				pass

			try:
				got = self.common.getVData(vid, useCache, saveCache)
				if got:
					return got
			except:
				pass

			if postIfMissing:
				# Ask tournesol to fetch the video
				resp = self.common.call_post(f"/video/", body={'video_id': vid[3:]}, jwt=self.jwt)
				if 'uid' not in resp:
					raise Exception(f"Could not fetch video {vid}")
				return self.common.getVData(vid, useCache, saveCache)
		return self._get_from_cache(vid)


	def getMyRateLater(self, saveCache=False) -> list[VData]:
		def onresult(res: list[VData]) -> bool:
			tmstp = timestamp()
			for vdata in res:
				self._cache_vdata(vdata, tmstp)
			if saveCache: self.saveCache()
			return True
		return self.common.callTournesolMulti('users/me/rate_later/videos', fn_continue=onresult, jwt=self.jwt)

	def getMyComparedVideos(self, useCache=True, saveCache=False, onlyCache=False) -> list[VData]:
		if not onlyCache:
			vids = set() if not useCache else set(self.videos)

			# only call tournesol for last comparisons (until "last_compared_at" is older than cache date)
			def check_need_update(res):
				last = res[-1]['entity']['uid']
				need_continue = ((last not in vids)
					or get(res[-1],'2000-00-00T00:00:00Z','individual_rating','last_compared_at') > get(self.videos[last],'2000-00-00T00:00:00Z','individual_rating','last_compared_at')
				)

				# Update new received videos data
				tmstp = timestamp()
				for vdata in res:
					self._cache_vdata(vdata, tmstp)

				if saveCache: self.saveCache()

				return need_continue
			self.common.callTournesolMulti('users/me/contributor_ratings/videos', 'order_by=-last_compared_at', fn_continue=check_need_update, jwt=self.jwt)

		return [self._get_from_cache(vid) for vid in self.videos]

	def getChannelVideos(self, channelTitle: str, onlyCache=False) -> dict[str, VData]:
		return self.common.getChannelVideos(channelTitle, onlyCache)


	def prettyPrintVData(self, vid: str|VData, useCache=True, saveCache=False) -> str:
		if isinstance(vid, str):
			return _pretty_print_vdata(self.getVData(vid, useCache=useCache, saveCache=saveCache))
		else:
			return _pretty_print_vdata(vid)


	#############
	##  CDATA  ##

	def getAllMyComparisons(self, useCache=True, saveCache=False, onlyCache=False) -> list[CData]:
		# TODO: When useCache=False and saveCache=True, remove any comparison present from cache that has not been fetched (update/create the others)
		out = self.comparisons if useCache else {}
		if not onlyCache:
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

					if useCache and cid not in out:
						need_continue = True # At least one new comparison has been found; will ask to get the next batch
					out[cid] = cdata
				if saveCache: self.saveCache()
				return need_continue

			self.common.callTournesolMulti('users/me/comparisons/videos', fn_continue=fn_continue, jwt=self.jwt)
		return list(out.values())

	def getMyComparisonsWith(self, vid, useCache=True, saveCache=False) -> list[CData]:
		# Check from cache if update is needed
		vdata1 = self.getVData(vid, useCache=True, saveCache=False)

		if useCache:
			expected_cmps = get(vdata1, 0, 'individual_rating', 'n_comparisons')
			cached_cmps = [cdata for cid,cdata in self.comparisons.items() if vid in cid.split('\t')]
			# All comparisons found in cache, no need to fetch API
			if expected_cmps == len(cached_cmps):
				return cached_cmps

		allRes = self.common.callTournesolMulti(f"users/me/comparisons/videos/{vid}/", jwt=self.jwt)
		tmstp = timestamp()

		for cdata in allRes:
			cdata['entity_a'] = cdata['entity_a']['uid']
			cdata['entity_b'] = cdata['entity_b']['uid']
			cdata['cached'] = tmstp
			cid = '\t'.join(sorted([cdata['entity_a'], cdata['entity_b']]))
			self.comparisons[cid] = cdata

		if saveCache: self.saveCache()
		# {
		#	entity_a: "yt:xxxxx",
		#	entity_b: "yt:xxxxx",
		#	cached: "2024-12-31T23:59:59Z",
		#	criteria_scores: [...],
		#	...
		# }
		return [cdata for cid,cdata in self.comparisons.items() if vid in cid.split('\t')]

	################
	##  REQUESTS  ##

	def postComparison(self, vid_neg:str, vid_pos:str, criteria_scores:dict[str,int], fake=False):
		# TODO: try/except if comparison is already existing, and backup to modifyExistingComparison
		if vid_neg[:3] != 'yt:': vid_neg = 'yt:' + vid_neg
		if vid_pos[:3] != 'yt:': vid_pos = 'yt:' + vid_pos

		body = {
			'entity_a': {'uid':vid_neg},
			'entity_b': {'uid':vid_pos},
			'criteria_scores':[{
				'criteria': crit,
				'score': cmp,
				'score_max': 10,
				'weight': 1,
			} for crit,cmp in criteria_scores.items()],
			'duration_ms': 0,
		}
		if fake:
			print(body)
		else:
			cdata:CData = self.common.call_post('users/me/comparisons/videos', body, jwt=self.jwt)
			cdata['cached'] = timestamp()
			self.comparisons['\t'.join(sorted([vid_neg, vid_pos]))] = cdata

	def setVideoAsPrivate(self, vid:str, setToPublic=False):
		if vid[:3] != 'yt:':
			vid = 'yt:' + vid[3:]

		vdata:VData = self.common.call_patch(f"users/me/contributor_ratings/videos/{vid}/", {"is_public":setToPublic}, jwt=self.jwt)
		self._cache_vdata(vdata, timestamp())

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

def get_individual_score(vdata: VData) -> float|None:
	arr = [s for s in get(vdata, [], 'individual_rating', 'criteria_scores') if s['criteria'] == 'largely_recommended']
	return arr[0]['score'] if arr else None

def _pretty_print_vdata(vdata: VData) -> str:
	if not 'entity' in vdata:
		return '[???]'

	vid = vdata['entity']['uid']

	score = None
	if ('collective_rating' in vdata
	 and vdata['collective_rating'] is not None
	 and 'tournesol_score' in vdata['collective_rating']
	 and vdata['collective_rating']['tournesol_score'] is not None
	):
		score = f" {vdata['collective_rating']['tournesol_score']:+3.0f}🌻 ({vdata['collective_rating']['n_comparisons']:4d}cmp/{vdata['collective_rating']['n_contributors']:3d}ctr)"

	if 'metadata' in vdata['entity'] and 'name' in vdata['entity']['metadata']:
		chn = vdata['entity']['metadata']['uploader'] or '???'
		nam = vdata['entity']['metadata']['name']
		return f"[{vid}]{'' if not score else score} {chn}: {nam}"

	return f"[{vid}]{'' if not score else score}"
