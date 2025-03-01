import zipfile

class TournesolUser:
	def __init__(self, sp: list[str]):
		try:
			self.public_username = sp[0]
			self.trust_score = float(sp[1] or '0')
		except:
			print(sp)
			raise

def extractAllTournesolUsers(zip) -> set[TournesolUser]:
	with zipfile.ZipFile(zip) as zip_file:
		with (zipfile.Path(zip_file) / 'users.csv').open(mode='r', encoding='utf-8') as cmpFile:
			# public_username,video_a,video_b,criteria,score

			users:set[TournesolUser] = set()

			# Skip first line (headers)
			cmpFile.readline()

			while True:
				line = cmpFile.readline()
				# if line is empty, end of file is reached
				if not line: break
				users.add(TournesolUser(line.strip().split(',')))

			return users
