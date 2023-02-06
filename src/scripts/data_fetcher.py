# %% IMPORTS
from model.channel import Channel, load_channels_data, save_new_channels_data
from model.video import Video, load_videos_data, save_new_videos_data
import model.youtube_api as ytAPI
from model.comparisons import ComparisonFile


def _list_missing_video_data(target_user: str, input_dir: str, vid_to_ignore: set[str]):
	missing_vids: set[str] = set()

	def check_add_missing_vid(ldata: list[str]):
		if ldata[0] == target_user: # Only interessed into videos compared by me
			if not (ldata[1] in vid_to_ignore):
				missing_vids.add(ldata[1])
			if not (ldata[2] in vid_to_ignore):
				missing_vids.add(ldata[2])

	ComparisonFile(input_dir).foreach(check_add_missing_vid)

	return list(missing_vids)

def _fetch_missing_data(CHANNELS, missing_vids):
	#
	# Requesting missing data
	#
	youtube = ytAPI.get_connection()
	data = []

	for i in range(0, len(missing_vids), ytAPI.INCREMENT):
		request = youtube.videos().list(
			part="id,snippet", # Information to get
			id= ','.join(missing_vids[i:i+ytAPI.INCREMENT]) # vid to get
		)
		data.extend(request.execute()['items'])

	#
	# Parsing youtube data output
	#
	newchannels = {}
	newvideos = {}
	for vdata in data:
		vid = vdata['id']
		vsnippet = vdata['snippet']

		cid = vsnippet['channelId']
		if not (cid in CHANNELS) and not (cid in newchannels):
			newchannels[cid] = Channel(cid, vsnippet['channelTitle'], vsnippet.get('defaultAudioLanguage', vsnippet.get('defaultLanguage', '??')))

		newvideos[vid] = Video(CHANNELS.get(cid, newchannels.get(cid)), vid, vsnippet['title'])


	#
	# Writing new data to cache
	#
	save_new_channels_data(newchannels)
	save_new_videos_data(newvideos)

def do_fetch_data(input_dir: str, target_user: str):
	# Load all cached data
	CHANNELS = load_channels_data() # {cid: Channel}
	VIDEOS = load_videos_data(CHANNELS) # {vid: Video}

	# Find missing video ids
	missing_vids = _list_missing_video_data(target_user, input_dir, VIDEOS.keys())
	if missing_vids:
		_fetch_missing_data(CHANNELS, missing_vids)

	# Output
	return {'channels': CHANNELS, 'videos': VIDEOS}
