from model.channel import Channel, load_channels_data, save_new_channels_data
from model.video import Video, load_videos_data, save_new_videos_data
import model.youtube_api as ytAPI
from model.comparisons import ComparisonFile, ComparisonLine


def _list_missing_video_data(target_user: str, input_dir: str, vid_to_ignore: set[str]):
	missing_vids: set[str] = set()

	def check_add_missing_vid(ldata: ComparisonLine):
		if ldata.user == target_user: # Only interessed into videos compared by me
			if not (ldata.vid1 in vid_to_ignore):
				missing_vids.add(ldata.vid1)
			if not (ldata.vid2 in vid_to_ignore):
				missing_vids.add(ldata.vid2)

	ComparisonFile(input_dir).foreach(check_add_missing_vid)

	return list(missing_vids)

def _fetch_missing_data(CHANNELS, VIDEOS, missing_vids):
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
		if not (cid in CHANNELS):
			newchannels[cid] = Channel(cid, vsnippet['channelTitle'], vsnippet.get('defaultAudioLanguage', vsnippet.get('defaultLanguage', '??')))
			CHANNELS[cid] = newchannels[cid]

		newvideos[vid] = Video(CHANNELS.get(cid, newchannels.get(cid)), vid, vsnippet['title'])
		VIDEOS[vid] = newvideos[vid]

	# Writing new data to cache
	save_new_channels_data(newchannels)
	save_new_videos_data(newvideos)

def do_fetch(input_dir: str, target_user: str):
	# Load all cached data
	print('Loading channels data...')
	CHANNELS = load_channels_data() # {cid: Channel}
	print(len(CHANNELS), 'channels cached.')

	print('Loading video data...')
	VIDEOS = load_videos_data(CHANNELS) # {vid: Video}
	print(len(VIDEOS), 'videos cached.')

	# Find missing video ids
	print('Finding missing video data...')
	missing_vids = _list_missing_video_data(target_user, input_dir, VIDEOS.keys())
	if missing_vids:
		print('Found', len(missing_vids), 'video missing: Fetching...')
		_fetch_missing_data(CHANNELS, VIDEOS, missing_vids)

	print('No more video data to fetch')
	print(len(VIDEOS), 'videos and', len(CHANNELS), 'channels listed')

	# Output
	return VIDEOS
