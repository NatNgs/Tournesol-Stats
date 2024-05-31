from typing import Callable

class ComparisonLine:
	def __init__(self, sp: dict[str,str]):
		try:
			# score,score_max,week_date
			self.user = sp['public_username']
			self.vid1 = sp['video_a']
			self.vid2 = sp['video_b']
			self.criterion = sp['criteria']
			self.score = int(float(sp['score']))
			self.date = sp['week_date']
		except:
			print(sp)
			raise


class ComparisonFile:
	def __init__(self, source):
		self.file_location = source + '/comparisons.csv'

	def foreach(self, fn: Callable[[ComparisonLine], None]):
		# public_username,video_a,video_b,criteria,score
		cmpFile = open(self.file_location, 'r', encoding='utf-8')

		# First line (headers)
		firstline = list(map(lambda s: s.strip(), cmpFile.readline().split(',')))

		while True:
			line = cmpFile.readline()
			# if line is empty, end of file is reached
			if not line:
				break

			spt = line.split(',')
			dta = {firstline[i]: spt[i].strip() for i in range(len(spt))}
			fn(ComparisonLine(dta))

		cmpFile.close()
