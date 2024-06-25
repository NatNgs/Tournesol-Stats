from __future__ import annotations
import os
import json
import math
import time
import pandas as pd
import datetime
import requests
import googleapiclient.http
import googleapiclient.discovery

API_KEY_LOCATION = os.path.expanduser('~/Documents/YT_API_KEY.txt')
MAX_FETCH_SIZE = 50

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


def _vdata_from_ytdata(data, cache:dict[str,Video]=None):
	#
	# Parsing youtube data output
	#
	newvideos:dict[str,any] = {}
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
				if 'metadata' in t_vdata['entity'] and 'language' in t_vdata['entity']['metadata']:
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

LAST_YT_CALL=datetime.datetime.now(datetime.timezone.utc)
def _fetch_video_data(videosToFetch: list[str], cache:dict[str,Video]|None):
	global LAST_YT_CALL
	#
	# Requesting missing data
	#
	youtube = _get_connection()
	newvideos = {}

	try:
		toFetch = len(videosToFetch)
		for i in range(0, toFetch, MAX_FETCH_SIZE):
			wait=(1.5)-(datetime.datetime.now(datetime.timezone.utc)-LAST_YT_CALL).total_seconds()
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
	for vid in videosToFetch:
		if not vid in newvideos:
			newvideos[vid] = {
				'vid': vid,
				'updated': nowDate
			}
	return newvideos


def _fetch_channel_data(channelsToFetch: list[str]):
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
			time.sleep(0.5) # Anti-spam
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

class Video(dict):
	def __init__(self, json: dict[str, any]):
		self.raw = json
		self.id: str = json['vid']
		self.channel: Channel = None

	def __setitem__(self, key, val):
		self.raw[key] = val

	def __getitem__(self, key):
		return self.raw.get(key)

	def get(self, key, default=None):
		return self.raw.get(key, default)

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

	def __str__(self):
		return self.short_str()

class Channel():
	def __init__(self, json: dict[str, any]):
		self.raw = json
		self.id: str = json['cid']

	def __getitem__(self, key):
		return self.get(key)

	def get(self, key, default=None):
		return self.raw.get(key, default)

	def __str__(self):
		if 'title' in self.raw:
			return self.raw['title']
		else:
			return f"[{self.id}]"

class YTData:
	def __init__(self):
		self.videos: dict[str, Video] = dict()
		self.channels: dict[str, Channel] = dict()

	def load(self, filename: str):
		vcnt = 0
		ccnt = 0
		with open(filename, 'r', encoding='UTF-8') as file:
			data = json.load(file)
			for v in data['VIDEOS']:
				if not v in self.videos or self.videos[v]['updated'] < data['VIDEOS'][v]['updated']:
					self.videos[v] = Video(data['VIDEOS'][v])
					vcnt += 1
			for c in data['CHANNELS']:
				if not c in self.channels or self.channels[c]['updated'] < data['CHANNELS'][c]['updated']:
					self.channels[c] = Channel(data['CHANNELS'][c])
					ccnt += 1
			print(f'YTData loaded from file {os.path.realpath(file.name)}')
			print(f'Loaded {vcnt} videos & {ccnt} channels.')
		self._update_vid_channel_links()

	def save(self, filename: str, print_log:bool = True):
		json_data = {
			'VIDEOS': {k:self.videos[k].raw for k in self.videos},
			'CHANNELS': {k:self.channels[k].raw for k in self.channels}
		}
		with open(filename, 'w', encoding='UTF-8') as file:
			json.dump(
				json_data,
				file,
				indent=2,
				sort_keys=True,
				ensure_ascii=False
			)
			if print_log:
				print(f'YTData saved to file {os.path.realpath(file.name)}', flush=True)

	def update(self, vids=[], cachedDays=365, max_update=0, force=False, save=None):
		updateDate = (datetime.datetime.utcnow() + datetime.timedelta(days=-cachedDays)).isoformat() + 'Z'

		# Find videos to update
		vidsToUpdate: set[str] = set()
		for v in vids:
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
					self.videos[vid] = Video(newvideos[vid])
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
				self.channels[cid] = Channel(newchannels[cid])
			if save:
				self.save(save, print_log=False)
		if toFetch > 0:
			print(f'Fetched {toFetch}/{toFetch} channels.')

		self._update_vid_channel_links()

	def _update_vid_channel_links(self):
		for vdata in self.videos:
			vdata: Video = self.videos[vdata]
			if vdata['cid'] and vdata['cid'] in self.channels:
				vdata.channel = self.channels[vdata['cid']]

	def load_ytHistory(self, history_file: str, removeOthers=False):
		# Add seen videos from yt history
		with open(history_file, 'r') as file:
			data: list[dict] = json.load(file)
			# Extract vid from videos urls
			vids = [d['titleUrl'].split('\u003d',2)[1] for d in data if 'titleUrl' in d]

		self.update(vids)

		if removeOthers:
			for toRm in list(self.videos.keys()):
				if toRm not in vids:
					self.videos.pop(toRm)
			print(f"Kept {len(self.videos)} videos from History.")
