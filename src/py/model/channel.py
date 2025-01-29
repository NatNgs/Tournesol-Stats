from __future__ import annotations
from model.video import Video


class Channel:
	def __init__(self, id: str, name: str):
		self.id = id
		self.name = name
		self.videos:dict[str,Video] = {}

	def add(self, video: Video):
		self.videos[video.id] = video

	def __str__(self):
		return f"[{self.id}] {self.name} ({self.lang})"


class __Channels:
	def __init__(self) -> None:
		self.__CHANNELS:dict[str,Channel] = {}

	def get(self, channelid:str) -> Channel|None:
		return self.__CHANNELS.get(channelid, None)

	def get_or_create(self, channelid:str, channelname:str) -> Channel:
		if channelid not in self.__CHANNELS:
			self.__CHANNELS[channelid] = Channel(channelid, channelname)
		if channelname is not None:
			self.__CHANNELS[channelid].name = channelname
		return self.__CHANNELS[channelid]

	def export(self):
		return [{
			'id': c.id,
			'name': c.name,
			# c.video not to be saved (exported in Video.channel)
		} for c in self.__CHANNELS.values()]

	def load(self, json:list[dict[str,str]]):
		for c in json:
			Channels.get_or_create(c['id'], c['name'])

Channels = __Channels()
