from typing import Callable

class TournesolUser:
	def __init__(self, sp: list[str]):
		try:
			self.public_username = sp[0]
			self.trust_score = float(sp[1] or '0')
		except:
			print(sp)
			raise

def extractAllTournesolUsers(source) -> set[TournesolUser]:
	file_location = source + '/users.csv'

	users:set[TournesolUser] = set()

	# public_username,video_a,video_b,criteria,score
	cmpFile = open(file_location, 'r', encoding='utf-8')
	# Skip first line (headers)
	cmpFile.readline()

	while True:
		line = cmpFile.readline()
		# if line is empty, end of file is reached
		if not line:
			break
		users.add(TournesolUser(line.strip().split(',')))

	cmpFile.close()
	return users
