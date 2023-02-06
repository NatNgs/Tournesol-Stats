FILE_LOCATION = 'data/cache/channel_info.tsv'

class Channel:
	def __init__(self, id: str, name: str, lang: str):
		self.id = id
		self.name = name
		self.lang = lang

	def __str__(self):
		return f"[{self.id}] {self.name} ({self.lang})"

def load_channels_data():
	# channelid \t lang \t channelname
	file = open(FILE_LOCATION, 'r', encoding='utf-8')

	channels: dict[str, Channel] = dict() # {cid: Channel}
	while True:
		line = file.readline()
		# if line is empty, end of file is reached
		if not line:
			break

		ldata = line.split('\t')
		channels[ldata[0]] = Channel(ldata[0], ldata[1], ldata[2])
	file.close()
	return channels

def save_new_channels_data(channels: dict[str, Channel]):
	# channelid \t lang \t channelname
	file = open(FILE_LOCATION, 'a', encoding='utf-8')

	ordered = list(channels.values())
	ordered.sort(key=lambda c: (c.lang, c.id))

	for channel in ordered:
		file.write(f"{channel.id}\t{channel.lang}\t{channel.name}\n")
		print('New channel data saved:', channel)
	file.close()
