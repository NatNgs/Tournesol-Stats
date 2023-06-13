from typing import Callable, Iterable

class CCSLine:
	def __init__(self, sp: list[str]):
		try:
			self.video = sp[0]
			self.criteria = sp[1]
			self.score = float(sp[2])
			self.uncertainty = float(sp[3])
		except:
			print(sp)
			raise


class CollectiveCriteriaScoresFile:
	def __init__(self, source):
		self.file_location = source + '/collective_criteria_scores.csv'

	def foreach(self, fn: Callable[[CCSLine], None]):
		# video,criteria,score,uncertainty
		cmpFile = open(self.file_location, 'r', encoding='utf-8')
		# Skip first line (headers)
		cmpFile.readline()

		while True:
			line = cmpFile.readline()
			# if line is empty, end of file is reached
			if not line:
				break
			fn(CCSLine(line.strip().split(',')))

		cmpFile.close()

	def get_vids_scores(self, criteria: str, vids: Iterable[str]=None, ignored: Iterable[str]=None):
		vids_scores: dict[str, float] = dict()
		def parse_line(line: CCSLine):
			if criteria == line.criteria and (vids == None or line.video in vids) and (ignored == None or line.video not in ignored):
				vids_scores[line.video] = line.score
		self.foreach(parse_line)
		return vids_scores
