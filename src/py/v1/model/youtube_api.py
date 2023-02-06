import googleapiclient.discovery

FILE_LOCATION = 'data/YT_API_KEY.txt'
INCREMENT = 50

def _get_yt_key():
	file = open(FILE_LOCATION, 'r', encoding='utf-8')
	key = "".join(file.readlines()).strip()
	file.close()
	return key

def get_connection():
	return googleapiclient.discovery.build('youtube', 'v3', developerKey = _get_yt_key())
