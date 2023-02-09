from typing import Callable

class ComparisonLine:
	def __init__(self, sp: list[str]):
		try:
			self.user = sp[0]
			self.vid1 = sp[1]
			self.vid2 = sp[2]
			self.criteria = sp[3]
			self.score = int(float(sp[4]))
		except:
			print(sp)
			raise


class ComparisonFile:
	def __init__(self, source):
		self.file_location = source + '/comparisons.csv'

	def foreach(self, fn: Callable[[ComparisonLine], None]):
		# public_username,video_a,video_b,criteria,score
		cmpFile = open(self.file_location, 'r', encoding='utf-8')
		# Skip first line (headers)
		cmpFile.readline()

		while True:
			line = cmpFile.readline()
			# if line is empty, end of file is reached
			if not line:
				break
			fn(ComparisonLine(line.strip().split(',')))

		cmpFile.close()
