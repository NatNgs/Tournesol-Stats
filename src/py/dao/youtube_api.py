# REQUIRES: pip install google-api-python-client

from __future__ import annotations
import os
import math
import time
import pandas as pd
import datetime
import requests
import googleapiclient.http
import googleapiclient.discovery
from utils.save import load_json_gz, save_json_gz


API_KEY_LOCATION = os.path.expanduser('~/Documents/YT_API_KEY.txt')
MAX_FETCH_SIZE = 50
YT_API_DELAY = 0.25 # seconds between 2 calls to youtube API

def _get_yt_key():
	file = open(API_KEY_LOCATION, 'r', encoding='utf-8')
	key = "".join(file.readlines()).strip()
	file.close()
	return key

def _get_connection() -> googleapiclient.discovery.Resource:
	return googleapiclient.discovery.build('youtube', 'v3', developerKey = _get_yt_key())


LAST_TNSL_CALL=datetime.datetime.now(datetime.timezone.utc)
VData=dict # type
def _fetch_tournesol(path):
	global LAST_TNSL_CALL
	BASE_URL='https://api.tournesol.app/'
	wait=1-(datetime.datetime.now(datetime.timezone.utc)-LAST_TNSL_CALL).total_seconds()
	if wait > 0:
		time.sleep(wait)
	print('\tGET', BASE_URL + path)
	response = requests.get(BASE_URL + path)
	LAST_TNSL_CALL = datetime.datetime.now(datetime.timezone.utc)
	return response.json()

def timestamp():
	return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec='seconds')

def _vdata_from_ytdata(data, cache:dict[str,YTVideo]=None) -> dict[str,any]:
	#
	# Parsing youtube data output
	#
	newvideos:dict[str,YTVideo] = {}
	nowDate = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
	for vdata in data:
		vid = vdata['id']

		newvideo = {'vid': vid, 'updated': nowDate}
		newvideos[vid] = newvideo

		defaultLng = '??'
		if 'snippet' in vdata:
			vsnippet = vdata['snippet']
			if 'title' in vsnippet: newvideo['title'] = vsnippet['title'].strip()
			if 'channelId' in vsnippet: newvideo['cid'] = vsnippet['channelId']
			if 'tags' in vsnippet: newvideo['tags'] = vsnippet['tags']
			if 'categoryId' in vsnippet: newvideo['category'] = int(vsnippet['categoryId'])
			if 'publishedAt' in vsnippet: newvideo['date'] = vsnippet['publishedAt']
			defaultLng = vsnippet.get('defaultAudioLanguage', vsnippet.get('defaultLanguage', '??'))[:2]

		if 'statistics' in vdata:
			vstatistics = vdata['statistics']
			if 'viewCount' in vstatistics: newvideo['viewCount'] = int(vstatistics['viewCount'])
			if 'likeCount' in vstatistics: newvideo['likeCount'] = int(vstatistics['likeCount'])
			if 'favoriteCount' in vstatistics: newvideo['favoriteCount'] = int(vstatistics['favoriteCount'])
			if 'commentCount' in vstatistics: newvideo['commentCount'] = int(vstatistics['commentCount'])

		# Localisations
		localizations = {d.strip()[:2] for d in vdata.get('localizations', {})}
		localizations.discard('')
		newvideo['localizations'] = list(localizations)

		if defaultLng == '??' and len(localizations) == 1:
			for l in localizations:
				defaultLng = l
		newvideo['defaultLng'] = defaultLng
		if defaultLng == '??':
			# Missing youtube data: Enrich with tournesolData
			if cache and cache.get(vid,{}).get('defaultLng','??') != '??':
				defaultLng = cache[vid]['defaultLng']
			else:
				t_vdata = _fetch_tournesol(f"polls/videos/entities/yt:{vid}")
				if 'entity' in t_vdata and 'metadata' in t_vdata['entity'] and 'language' in t_vdata['entity']['metadata']:
					newvideo['defaultLng'] = t_vdata['entity']['metadata']['language'] or '??'
		if defaultLng != '??':
			localizations.add(defaultLng)

		# Tags, duration, definition
		if 'contentDetails' in vdata:
			vcontent = vdata['contentDetails']
			if 'duration' in vcontent: newvideo['duration'] = int(pd.Timedelta(vcontent['duration']).total_seconds()) # "PT13M40S" => 00:13:40 > int(13*60+40)
			if 'definition' in vcontent: newvideo['definition'] = vcontent['definition'] # "hd"

		if 'topicDetails' in vdata:
			newvideo['topics'] = [t.split('/')[-1].replace('_', ' ')
				for t in vdata['topicDetails'].get('topicCategories', []) # t: 'https://<??>.wikipedia.org/wiki/<Topic>
			]

	return newvideos

def _cdata_from_ytcdata(ytdata):
	cdata = {'cid': ytdata['id']}

	if 'snippet' in ytdata:
		vsnippet = ytdata['snippet']
		if 'title' in vsnippet: cdata['title'] = vsnippet['title'].strip()
		if 'publishedAt' in vsnippet: cdata['published'] = vsnippet['publishedAt']
		if 'country' in vsnippet: cdata['country'] = vsnippet['country']
		if 'customUrl' in vsnippet: cdata['handle'] = vsnippet['customUrl']

	vstatistics = ytdata['statistics']
	cdata['viewCount'] = int(vstatistics['viewCount'])
	cdata['subCount'] = int(vstatistics['subscriberCount'])
	cdata['videoCount'] = int(vstatistics['videoCount'])

	localizations = {d.strip()[:2] for d in ytdata.get('localizations', {})}
	localizations.discard('')
	cdata['localizations'] = list(localizations)

	cdata['topics'] = [t.split('/')[-1].replace('_', ' ')
		for t in ytdata.get('topicDetails', {}).get('topicCategories', []) # t: 'https://<??>.wikipedia.org/wiki/<Topic>
	]

	cdata['playlists'] = {}
	rel_playlists = ytdata.get('contentDetails', {}).get('relatedPlaylists', {})
	for playlist_name in rel_playlists:
		if rel_playlists[playlist_name]:
			cdata['playlists'][playlist_name] = rel_playlists[playlist_name]

	return cdata

LAST_YT_CALL=datetime.datetime.now(datetime.timezone.utc)

@DeprecationWarning # Use YoutubeAPI.get_videos_data instead
def _fetch_video_data(vids: list[str], cache:dict[str,YTVideo]|None, ignore_cached=False) -> dict[str,YTVideo]:
	global LAST_YT_CALL
	youtube = _get_connection()
	newvideos = {}
	if ignore_cached and cache:
		newvideos = {v:cache[v] for v in vids if v in cache}
		videosToFetch = [v for v in vids if v not in newvideos]

	try:
		toFetch = len(videosToFetch)
		for i in range(0, toFetch, MAX_FETCH_SIZE):
			wait=YT_API_DELAY-(datetime.datetime.now(datetime.timezone.utc)-LAST_YT_CALL).total_seconds()
			if wait > 0:
				time.sleep(wait)
			request: googleapiclient.http.HttpRequest = youtube.videos().list(
				part='id,snippet,statistics,localizations,contentDetails,topicDetails', # Information to get
				id= ','.join(videosToFetch[i:i+MAX_FETCH_SIZE]) # vid to get
			)
			response = request.execute()['items']
			LAST_YT_CALL = datetime.datetime.now(datetime.timezone.utc)
			resp = _vdata_from_ytdata(response, cache=cache)
			newvideos.update(resp)
	except Exception as e:
		print('Fetch failed.')
		raise e

	nowDate = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
	for vid in vids:
		if not vid in newvideos:
			newvideos[vid] = {
				'vid': vid,
				'updated': nowDate
			}

	return newvideos


def _fetch_channel_data(channelsToFetch: list[str]) -> dict[str, YTChannel]:
	#
	# Requesting missing data
	#
	youtube = _get_connection()
	data = []

	try:
		toFetch = len(channelsToFetch)
		for i in range(0, toFetch, MAX_FETCH_SIZE):
			request: googleapiclient.http.HttpRequest = youtube.channels().list(
				part='id,snippet,statistics,topicDetails', # Information to get
				id= ','.join(channelsToFetch[i:i+MAX_FETCH_SIZE]) # cid to get
			)
			data.extend(request.execute()['items'])
			time.sleep(YT_API_DELAY) # Anti-spam
	except Exception as e:
		print('Fetch failed.')
		raise e

	#
	# Parsing youtube data output
	#
	newchannels = {}
	nowDate = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
	for cdata in data:
		cid = cdata['id']

		newcdata = {'cid': cid, 'updated': nowDate}
		newchannels[cid] = newcdata

		if 'snippet' in cdata:
			vsnippet = cdata['snippet']
			if 'title' in vsnippet: newcdata['title'] = vsnippet['title'].strip()
			if 'publishedAt' in vsnippet: newcdata['published'] = vsnippet['publishedAt']
			if 'country' in vsnippet: newcdata['country'] = vsnippet['country']

		vstatistics = cdata['statistics']
		newcdata['viewCount'] = int(vstatistics['viewCount'])
		newcdata['subCount'] = int(vstatistics['subscriberCount'])
		newcdata['videoCount'] = int(vstatistics['videoCount'])

		localizations = {d.strip()[:2] for d in cdata.get('localizations', {})}
		localizations.discard('')
		newcdata['localizations'] = list(localizations)

		newcdata['topics'] = [t.split('/')[-1].replace('_', ' ')
			for t in cdata.get('topicDetails', {}).get('topicCategories', []) # t: 'https://<??>.wikipedia.org/wiki/<Topic>
		]

	for cid in channelsToFetch:
		if not cid in newchannels:
			newchannels[cid] = {
				'cid': cid,
				'updated': nowDate
			}

	return newchannels


class YTVideo():
	def __init__(self, json: dict[str, any]):
		self.raw = json
		self.id: str = json['vid']
		self.channel: YTChannel = None

	def __setitem__(self, key, val):
		self.raw[key] = val

	def __getitem__(self, key):
		return self.raw.get(key)

	def get(self, default=None, *keys):
		d = self.raw
		for k in keys:
			if k in d:
				d = d[k]
			else:
				return default
		return d

	def short_str(self):
		if 'title' in self.raw:
			if self.channel:
				return f"{self.channel}: {self.raw['title']}"
			return f"(?): {self.raw['title']}"
		return f"[{self.id}]"

	def long_str(self):
		if 'title' in self.raw:
			if self.channel:
				return f"[{self.id}] {self.channel}: {self.raw['title']}"
			return f"[{self.id}] (Unknown channel): {self.raw['title']}"
		return f"[{self.id}]"

	def __repr__(self):
		return f"<Video {self.id}" + (f" by {self.channel.__repr__()}" if self.channel else '') + '>'
	def __str__(self):
		return self.short_str()

class YTChannel():
	def __init__(self, json: dict[str, any]):
		self.raw = json
		self.id: str = json['cid']
		self.handle: str = json.get('handle', None)
		self.videos: dict[str, YTVideo] = {}

	def __getitem__(self, key):
		return self.get(key)

	def get(self, key, default=None):
		return self.raw.get(key, default)

	def title(self):
		return self.raw.get('title', self.handle if self.handle else self.id)

	def __repr__(self):
		handle = self.handle if self.handle else self.id
		title = f" \"{self.raw['title']}\"" if 'title' in self.raw else ''
		return f"<Channel {handle}{title}>"

	def __str__(self):
		if 'title' in self.raw:
			return self.raw['title']
		else:
			return f"[{self.id}]"

@DeprecationWarning # Use YoutubeAPI instead
class YTData:
	def __init__(self):
		self.videos: dict[str, YTVideo] = dict()
		self.channels: dict[str, YTChannel] = dict()

	def load(self, filename: str):
		vcnt = 0
		ccnt = 0

		unloaded_data = load_json_gz(filename)

		for v in unloaded_data['VIDEOS']:
			if not v in self.videos or self.videos[v]['updated'] < unloaded_data['VIDEOS'][v]['updated']:
				self.videos[v] = YTVideo(unloaded_data['VIDEOS'][v])
				vcnt += 1
		for c in unloaded_data['CHANNELS']:
			if not c in self.channels or self.channels[c]['updated'] < unloaded_data['CHANNELS'][c]['updated']:
				self.channels[c] = YTChannel(unloaded_data['CHANNELS'][c])
				ccnt += 1
		print(f'Loaded {vcnt} videos & {ccnt} channels from cache')
		self._update_vid_channel_links()

	def save(self, filename: str, print_log:bool = True):
		json_data = {
			'VIDEOS': {k:self.videos[k].raw for k in self.videos},
			'CHANNELS': {k:self.channels[k].raw for k in self.channels}
		}

		savedfile = save_json_gz(filename, json_data)
		if print_log:
			print(f'YTData saved to file {savedfile}', flush=True)

	def update(self, vids=[], cachedDays=365, max_update=0, force=False, save=None):
		updateDate = (datetime.datetime.utcnow() + datetime.timedelta(days=-cachedDays)).isoformat() + 'Z'

		# Find videos to update
		vidsToUpdate: set[str] = set()
		for v in vids:
			if v[:3] == 'yt:':
				v = v[3:]
			if force or (not v in self.videos):
				vidsToUpdate.add(v)

		max_update = math.ceil(1.0*max(max_update, len(vidsToUpdate))/MAX_FETCH_SIZE)*MAX_FETCH_SIZE

		newV = len(vidsToUpdate)
		for vid in sorted(self.videos, key=lambda v: self.videos[v]['updated']):
			if len(vidsToUpdate) >= max_update \
				or self.videos[vid]['updated'] > updateDate:
				break
			vidsToUpdate.add(vid)

		# Update videos
		toFetch = len(vidsToUpdate)
		if toFetch > 0:
			print(f"{newV} new videos to fetch + {toFetch-newV} to be updated")

			for chunk in range(0, toFetch, MAX_FETCH_SIZE):
				print(f"Fetching {chunk}/{toFetch} videos...")
				newvideos = _fetch_video_data(list(vidsToUpdate)[chunk:chunk+MAX_FETCH_SIZE], self.videos)
				for vid in newvideos:
					self.videos[vid] = YTVideo(newvideos[vid])
				if save:
					self.save(save, print_log=False)
			print(f'Fetched {toFetch}/{toFetch} videos.')

		###

		# Find channels to update
		channelsToUpdate: set[str] = set()
		for vid in self.videos:
			cid = self.videos[vid]['cid']
			if cid  and (   (force and vid in vids) # Force update channels of given videos
					or (cid not in self.channels) # Update unknown channels
					or (self.channels[cid]['updated'] < updateDate)
				):
					channelsToUpdate.add(cid)

		# Update channels
		toFetch = len(channelsToUpdate)
		for chunk in range(0, toFetch, MAX_FETCH_SIZE):
			print(f"Fetching {chunk}/{toFetch} channels...")
			newchannels = _fetch_channel_data(list(channelsToUpdate)[chunk:chunk+MAX_FETCH_SIZE])
			for cid in newchannels:
				self.channels[cid] = YTChannel(newchannels[cid])
			if save:
				self.save(save, print_log=False)
		if toFetch > 0:
			print(f'Fetched {toFetch}/{toFetch} channels.')

		self._update_vid_channel_links()

	def _update_vid_channel_links(self):
		for vdata in self.videos:
			vdata: YTVideo = self.videos[vdata]
			if vdata['cid'] and vdata['cid'] in self.channels:
				vdata.channel = self.channels[vdata['cid']]

	def load_ytHistory(self, history_file: str, removeOthers=False):
		# Add seen videos from yt history
		data:list[dict] = load_json_gz(history_file)
		# Extract vid from videos urls
		vids = [d['titleUrl'].split('\u003d',2)[1] for d in data if 'titleUrl' in d]

		self.update(vids)

		if removeOthers:
			for toRm in list(self.videos.keys()):
				if toRm not in vids:
					self.videos.pop(toRm)
			print(f"Kept {len(self.videos)} videos from History.")

	def get_videos_data(self, vids: list[str]) -> dict[str,YTVideo]:
		#
		# Requesting missing data
		#
		global LAST_YT_CALL
		youtube = _get_connection()
		newvideos = {}
		newvideos = {v:self.videos[v] for v in vids if v in self.videos}
		# TODO: Still fetch depending on self.videos[#].updated date (to refresh every often)
		videosToFetch = [v for v in vids if v not in newvideos]

		if videosToFetch:
			try:
				toFetch = len(videosToFetch)
				print(f"[YTAPI] GET videos data... ({len(toFetch)})", end=' ')
				for i in range(0, toFetch, MAX_FETCH_SIZE):
					print(i+len(subsample), end=' ')
					subsample = videosToFetch[i:i+MAX_FETCH_SIZE]
					wait=YT_API_DELAY-(datetime.datetime.now(datetime.timezone.utc)-LAST_YT_CALL).total_seconds()
					if wait > 0:
						time.sleep(wait)
					request: googleapiclient.http.HttpRequest = youtube.videos().list(
						part='id,snippet,statistics,localizations,contentDetails,topicDetails', # Information to get
						id= ','.join(subsample) # vid to get
					)
					response = request.execute()['items']
					LAST_YT_CALL = datetime.datetime.now(datetime.timezone.utc)
					resp = _vdata_from_ytdata(response, cache=self.videos)
					newvideos.update(resp)
				print('.')
			except Exception as e:
				print('Fetch failed.')
				raise e

		nowDate = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
		for vid in vids:
			if not vid in newvideos:
				newvideos[vid] = {
					'vid': vid,
					'updated': nowDate
				}

		return newvideos



class YoutubeAPIDelay:
	"""
	Usage:
		with YoutubeAPIDelay(YTAPI):
			# call to Youtube API
	"""
	def __init__(self, api:YoutubeAPI):
		self.api = api

	def __enter__(self):
		wait=self.api._delay-(time.time()-self.api._last_api_call)
		if wait > 0:
			time.sleep(wait)

	def __exit__(self, type, value, traceback):
		self.api._last_api_call = time.time()


class YoutubeAPI:
	def __init__(self):
		self.videos: dict[str, YTVideo] = dict() # YT video ID (11 char)
		self.channels: dict[str, YTChannel] = dict() # YT channel id (Uxxxxxxxxxxxxx)

		# YoutubeAPIDelay
		self._delay = .25
		self._last_api_call = time.time()

		# Cache file
		self.autosave:str = None

	def _update_vid_channel_links(self, vids:list[str]=None):
		# Update Channel and Video objects links
		remv = 0
		cnct = 0
		for vid in (vids or self.videos):
			if not vid in self.videos:
				continue
			vdata: YTVideo = self.videos[vid]
			if not isinstance(vdata, YTVideo):
				raise f"!!! _update_vid_channel_links : YTAPI.videos[{vid}] is not a video: = {vdata} !!!"
			if vdata['cid'] and vdata['cid'] in self.channels:
				vdata.channel = self.channels[vdata['cid']]
				self.channels[vdata['cid']].videos[vid] = vdata
				cnct += 1
		if remv > 0:
			print()
		if cnct > 0:
			print('_update_vid_channel_links connected', cnct, 'videos to their channels')

	### Files ###

	def load(self, filename: str, autosave=False):
		vcnt = 0
		ccnt = 0

		unloaded_data = None
		try:
			unloaded_data = load_json_gz(filename)
		except Exception as e:
			print(f"Error while loading cache file {filename}: {e}")

		if unloaded_data:
			for v in unloaded_data['VIDEOS']:
				if not v in self.videos or self.videos[v]['updated'] < unloaded_data['VIDEOS'][v]['updated']:
					self.videos[v] = YTVideo(unloaded_data['VIDEOS'][v])
					vcnt += 1
			for c in unloaded_data['CHANNELS']:
				if not c in self.channels or self.channels[c]['updated'] < unloaded_data['CHANNELS'][c]['updated']:
					self.channels[c] = YTChannel(unloaded_data['CHANNELS'][c])
					ccnt += 1
			print(f'Loaded {vcnt} videos & {ccnt} channels from cache')

			self._update_vid_channel_links()

		if autosave:
			self.autosave = filename
			if not unloaded_data:
				self.save(filename, print_log=True)

	def save(self, filename: str, print_log:bool = True):
		json_data = {
			'VIDEOS': {k:self.videos[k].raw for k in self.videos},
			'CHANNELS': {k:self.channels[k].raw for k in self.channels}
		}

		savedfile = save_json_gz(filename, json_data)
		if print_log:
			print(f'YTData saved to file {savedfile}', flush=True)


	### API ###

	def get_channel(self, *, handle:str=None, ytid:str=None) -> YTChannel:
		if not handle and not ytid:
			raise ValueError("Neither handle nor ytid parameters has been set")
		if handle and ytid:
			raise ValueError("Only one of handle & ytid parameters can be set")

		# Lookup in cache
		if handle is not None:
			if handle[0] != '@':
				handle = '@' + handle
			handle = handle.lower()
		for c in self.channels.values():
			if (handle and c.handle == handle) or (ytid and c.id == ytid):
				return c

		requested_channel = None
		try:
			youtube = _get_connection()
			print(f"[YTAPI] Get channel {handle or ytid}...")
			request: googleapiclient.http.HttpRequest = youtube.channels().list(
				part='id,snippet,statistics,topicDetails,contentDetails', # Information to get
				forHandle=handle if handle else None,
				id=ytid if ytid else None
			)
			with YoutubeAPIDelay(self):
				result = request.execute()

			nowdate = timestamp()
			for ytcdata in result['items']:
				cdata = _cdata_from_ytcdata(ytcdata)
				cdata['updated'] = nowdate
				cid = cdata['cid']
				requested_channel = self.channels[cid] = YTChannel(cdata)

			if self.autosave:
				self.save(self.autosave, print_log=False)
		except Exception as e:
			print('Fetch failed.')
			raise e
		return requested_channel

	def get_channels_by_id(self, cids:list[str], max_cache_refresh:int=100, max_video:int=0) -> dict[str, YTChannel]:
		# Get data from cache
		requested_cdata = {c: self.channels[c] for c in cids if c in self.channels}

		# Requesting missing data
		toFetch = [c for c in cids if c not in requested_cdata]
		# Also request channels not updated for a certain time
		for cid,channel in sorted(requested_cdata.items(), key=lambda x: x[1].raw['updated']):
			last_fetch = datetime.datetime.fromisoformat(channel.raw['updated'])
			current = datetime.datetime.now(datetime.timezone.utc)
			elapsed = (current - last_fetch).days
			if elapsed <= 7:
				break
			toFetch.append(cid)
			if len(toFetch) >= max_cache_refresh:
				break

		if toFetch:
			fetched = []
			try:
				youtube = _get_connection()
				print(f"[YTAPI] Get channels data... (/{len(toFetch)})", end=' ')
				for i in range(0, len(toFetch), MAX_FETCH_SIZE):
					subsample = toFetch[i:i+MAX_FETCH_SIZE]
					request: googleapiclient.http.HttpRequest = youtube.channels().list(
						part='id,snippet,statistics,topicDetails,contentDetails', # Information to get
						id= ','.join(subsample) # cid to get
					)
					with YoutubeAPIDelay(self):
						result = request.execute()

					nowdate = timestamp()
					for ytcdata in result['items']:
						cdata = _cdata_from_ytcdata(ytcdata)
						cdata['updated'] = nowdate
						cid = cdata['cid']
						self.channels[cid] = requested_cdata[cid] = YTChannel(cdata)
						fetched.append(cid)

					if self.autosave:
						self.save(self.autosave, print_log=False)
					if len(fetched) >= max_video:
						break

					print(len(fetched), end=' ')
				print('.')
				self._update_vid_channel_links()
			except Exception as e:
				print('Fetch failed.')
				raise e

		# Set blank data if could not fetch
		if len(requested_cdata) < len(cids):
			nowdate = timestamp()
			for cid in cids:
				if not cid in requested_cdata:
					self.channels[cid] = requested_cdata[cid] = YTChannel({'cid': cid, 'updated': nowdate})

			if self.autosave:
				self.save(self.autosave, print_log=False)

		return requested_cdata

	def get_videos_data(self, vids:list[str]) -> dict[str,YTVideo]:
		# Get data from cache
		requested_vdata = {v:self.videos[v] for v in vids if v in self.videos}

		# Requesting missing data
		toFetch = [v for v in vids if v not in requested_vdata]
		# Also request videos not updated for a certain time
		for vid,video in requested_vdata.items():
			if len(toFetch) > 0 and len(toFetch) % MAX_FETCH_SIZE == 0:
				break
			last_fetch = datetime.datetime.fromisoformat(video.raw['updated'])
			current = datetime.datetime.now(datetime.timezone.utc)
			elapsed = (current - last_fetch).days
			if elapsed > 90:
				toFetch.append(vid)

		if toFetch:
			try:
				youtube = _get_connection()
				fetched = []
				print(f"[YTAPI] Get videos data... (/{len(toFetch)})", end=' ')
				for i in range(0, len(toFetch), MAX_FETCH_SIZE):
					subsample = toFetch[i:i+MAX_FETCH_SIZE]

					request: googleapiclient.http.HttpRequest = youtube.videos().list(
						part='id,snippet,statistics,localizations,contentDetails,topicDetails', # Information to get
						id= ','.join(subsample) # videos to get
					)
					with YoutubeAPIDelay(self):
						response = request.execute()['items']

					for vid,vdata in _vdata_from_ytdata(response, cache=self.videos).items():
						vdata['updated'] = timestamp()
						fetched.append(vid)
						requested_vdata[vid] = YTVideo(vdata)
						self.videos[vid] = requested_vdata[vid]

					if self.autosave:
						self.save(self.autosave, print_log=False)

					print(len(fetched), end=' ')
				self._update_vid_channel_links(fetched)
				print('.')
			except Exception as e:
				print('[YTAPI] Fetch failed.')
				raise e

		# Set blank data if could not fetch
		if len(requested_vdata) < len(vids):
			nowDate = timestamp()
			for vid in vids:
				if not vid in requested_vdata:
					self.videos[vid] = YTVideo({
						'vid': vid,
						'updated': nowDate
					})
					requested_vdata[vid] = self.videos[vid]

			if self.autosave:
				self.save(self.autosave, print_log=False)

		return requested_vdata

	def get_channel_videos(self, *, channel:YTChannel=None, channelHandle:str=None, onlyCache:bool=False) -> dict[str,YTVideo]:
		# Fetch channel data
		if not channel and not channelHandle:
			raise ValueError('Either channel or channelHandle must be set')
		if not channel:
			channel = self.get_channel(handle=channelHandle)
			if not channel:
				print(f'[YTAPI] get_channel_videos: Channel {channelHandle} not found')
				return []
		channelHandle = channel.handle

		# Check if last fetch was recent
		if 'last_fetch_uploads' in channel.raw:
			last_fetch = datetime.datetime.fromisoformat(channel.raw['last_fetch_uploads'])
			current = datetime.datetime.now(tz=datetime.timezone.utc)
			elapsed = (current - last_fetch).days
			if onlyCache or elapsed <= 31:
				return channel.videos

		try:
			youtube = _get_connection()

			# Fetch uploads playlist
			if not 'uploads' in channel.raw['playlists']:
				print(f"[YTAPI] No playlist {channelHandle}/uploads found")
				return

			# Fetch videos from playlist
			doContinue = True
			nextPage=None
			total=None
			page=1
			print(f"[YTAPI] Get videos from {channelHandle}/uploads...", end=' ')
			fetched = []
			while doContinue:
				request: googleapiclient.http.HttpRequest = youtube.playlistItems().list(
					playlistId=channel.raw['playlists']['uploads'],
					part='snippet', # Information to get
					maxResults=MAX_FETCH_SIZE,
					pageToken=nextPage,
				)

				with YoutubeAPIDelay(self):
					response = request.execute()

				# Get video data to cache
				fetched.extend(ytv['snippet']['resourceId']['videoId'] for ytv in response['items'])

				if not total:
					total = response['pageInfo']['totalResults']
					print(f"{len(fetched)}/{total}", end=' ')
				else:
					# If total results == current channel videos data: do not continue (we already know all videos in cache)
					print(len(fetched), end=' ')

				nextPage=response.get('nextPageToken', None)
				if not nextPage:
					doContinue = False
				else:
					page+=1
			channel.raw['last_fetch_uploads'] = timestamp()
			if self.autosave:
				self.save(self.autosave, print_log=False)
			print('.')

			# Fetch video data:
			return self.get_videos_data(fetched)
		except Exception as e:
			print('Fetch failed.')
			raise e
