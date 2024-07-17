import gzip
import json
import time
import datetime
import requests

# Type
VData=dict[str,any]
CData=dict[str,any]

def timestamp():
	return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec='seconds')

class TournesolAPI:
	def __init__(self, jwt:str, cache_file:str):
		self.file = cache_file
		self.jwt = jwt
		self.last_api_call=time.time()
		self.base_url='https://api.tournesol.app/'
		self.delay=1.0 # Seconds between call to API

		# Load cache
		self.cache:dict[str,dict[str,any]] = {
			'me/comparisons': {}, # "entity_a\tentity_b": {<cdata>}
			'me/videos': {}, # "vid": {vdata}
		}
		try:
			with gzip.open(self.file, 'rt', encoding='UTF-8') as file:
				loaded = json.load(file)
				for k in self.cache:
					if k in loaded:
						self.cache[k] = loaded[k]
		except:
			print('Failed to load file', self.file)

	def saveCache(self):
		with gzip.open(self.file, 'wt', encoding='UTF-8') as file:
			json.dump(self.cache, file)

	def callTournesol(self, path: str):
		if path[0] == '/': # Cut leading slash in path
			path = path[1:]

		wait=self.delay-(time.time()-self.last_api_call)
		if wait > 0:
			time.sleep(wait)
		response = requests.get(self.base_url + path, headers={'Authorization': self.jwt} if self.jwt else None)
		self.last_api_call = time.time()
		response.raise_for_status() # raises HTTPError (exc.response.status_code == 4xx or 5xx)
		return response.json()

	def callTournesolMulti(self, path: str, args:str=None, start:int=0, end:int=0, fn_continue=None) -> list[VData]:
		LIMIT=1000
		URL=f'{path}?limit={LIMIT}' + (('&' + args) if args else '')
		offset=start

		print(f"Calling TournesolAPI {path}...", end=' ')
		rs = self.callTournesol(URL + f'&offset={offset}')
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
			rs = self.callTournesol(URL + f'&offset={offset}')
			total = rs['count']
			last_res = rs['results']
			allRes += last_res
			print(f'{len(allRes)}', end=' ')
		print('.')

		return allRes


	def getVData(self, vid:str, useCache=False, saveCache=True) -> VData:
		if not useCache or vid not in self.cache['me/videos']:
			self.cache['me/videos'][vid] = self.callTournesol(f"users/me/contributor_ratings/videos/{vid}/")
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

	def getMyComparedVideos(self, useCache=False, saveCache=True) -> list[VData]:
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

	def getAllMyComparisons(self, useCache=False, saveCache=True) -> list[CData]:
		if not useCache:
			allRes = self.callTournesolMulti('users/me/comparisons/videos')
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
				self.getVData(cdata['entity_a'], useCache=True, saveCache=False)
				self.getVData(cdata['entity_b'], useCache=True, saveCache=False)

			if saveCache: self.saveCache()

		# {
		#	entity_a: "yt:xxxxx",
		#	entity_b: "yt:xxxxx",
		#	cached: "2024-12-31T23:59:59Z",
		#	criteria_scores: [...],
		#	...
		# }
		return self.cache['me/comparisons'].values()

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
