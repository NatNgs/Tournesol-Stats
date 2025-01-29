from __future__ import annotations
from model.channel import Channels
from model.comparison import Comparison

class Video(dict):
	def __init__(self, json: dict[str, any]):
		self.raw = json # Format like returned by <tournesol>/polls/videos/entities/<vid>
		""" raw = {
			"entity": {
				"uid": "yt:abcdefghijk",
				"type": "video",
				"metadata": {
					"name": "Video Title",
					"tags": ["tag1", "tag2"],
					"views": 123456789,
					"source": "youtube",
					"duration": 123,
					"language": "en",
					"uploader": "Channel name",
					"video_id": "abcdefghijk",
					"channel_id": "Uabcdefghijklmnopqrstuvw",
					"description": "Youtube video description",
					"is_unlisted": false,
					"publication_date": "2022-12-31T23:59:59Z"
				}
			},
			"entity_contexts": [],
			"collective_rating": {
				"n_comparisons": 123,
				"n_contributors": 123,
				"tournesol_score": 42.12345678901234,
				"unsafe": {
					"status": false,
					"reasons": []
				},
				"criteria_scores": [
					{"criteria": "backfire_risk", "score": 42.12345678901234},
					{"criteria": "better_habits", "score": 42.12345678901234},
					{"criteria": "diversity_inclusion, "score": 42.12345678901234},
					{"criteria": "engaging", "score": 42.12345678901234},
					{"criteria": "entertaining_relaxing", "score": 42.12345678901234},
					{"criteria": "importance", "score": 42.12345678901234},
					{"criteria": "largely_recommended", "score": 42.12345678901234},
					{"criteria": "layman_friendly", "score": 42.12345678901234},
					{"criteria": "pedagogy", "score": 42.12345678901234},
					{"criteria": "reliability", "score": 42.12345678901234},
				]
			},
			"recommendation_metadata": {
				"total_score": null
			}
		}
		"""

		self.id: str = json['entity']['uid'] # yt:abcdefghijk
		self.channel = Channels.get_or_create(json['entity']['metadata']['channel_id'], json['entity']['metadata']['uploader'])
		self.channel.add(self)

		self.comparisons:dict[str,Comparison] = {}

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

class __Videos:
	def __init__(self):
		self.__videos:dict[str,Video] = {}

	def get_or_create(self, vid:str, raw:dict[str,any]) -> Video:
		if vid not in self.__videos:
			self.__videos[vid] = Video(raw)
		return self.__videos[vid]

	def export(self):
		return [{
			'id': v.id,
			'channel': v.channel.id,
			'raw': v.raw,
			# v.comparisons not to be saved (exported in class Comparison)
		} for v in self.__videos.values()]

	def load(self, json:list[dict[str,str]]):
		for c in json:
			self.get_or_create(c['id'], c['name'])

Videos = __Videos()
