from typing import Callable, Iterable

class CCSLine:
	def __init__(self, sp: list[str]):
		try:
			self.video = sp[0]
			self.criterion = sp[1]
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

	def get_scores(self, criterion:str, vids: Iterable[str]=None) -> dict[str,dict[str,tuple[float,float]]]:
		"""
		Args:
			criterion (str, optional): Filter to given criterion only. None means no filtering on criteria.
			vids (Iterable[str], optional): List of video ids to extract. Empty list means no video. None means all videos.

		Returns:
			dict[str,dict[str,dict[str,tuple[float,float]]]]: `(score, uncertainty) = out[video][criterion]`
		"""
		data:dict[str,dict[str,tuple[float,float]]] = dict()

		def parse_line(line: CCSLine):
			if (not criterion or criterion == line.criterion) and (vids is None or line.video in vids):
				data.setdefault(line.video, dict())[line.criterion] = (line.score, line.uncertainty)
		self.foreach(parse_line)
		return data

	# deprecated
	def get_vids_scores(self, criterion: str, vids: Iterable[str]=None, ignored: Iterable[str]=None):
		vids_scores: dict[str, float] = dict()
		def parse_line(line: CCSLine):
			if criterion == line.criterion and (vids == None or line.video in vids) and (ignored == None or line.video not in ignored):
				vids_scores[line.video] = line.score
		self.foreach(parse_line)
		return vids_scores

	# deprecated
	def get_vids_scores_criteria(self, vids: Iterable[str]=None, ignored: Iterable[str]=None):
		vids_scores: dict[str, dict[str,float]] = dict()
		def parse_line(line: CCSLine):
			if (vids == None or line.video in vids) and (ignored == None or line.video not in ignored):
				vids_scores.setdefault(line.video, dict())[line.criterion] = line.score
		self.foreach(parse_line)
		return vids_scores # vids_scores[vid][criteria] = score
