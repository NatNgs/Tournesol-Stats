from typing import Callable, Iterable

class ICSLine:
	def __init__(self, sp: list[str]):
		try:
			# public_username,video,criteria,score,uncertainty,voting_right
			self.user: str = sp[0]
			self.video: str = sp[1]
			self.criterion: str = sp[2]
			self.score: float = float(sp[3]) # -100.0 - 100.0
			self.uncertainty = float(sp[4]) # 0.0 - 100.0
			self.voting_right = float(sp[5]) # 0.0 - 1.0
		except:
			print(sp)
			raise


class IndividualCriteriaScoresFile:
	def __init__(self, source):
		self.file_location = source + '/individual_criteria_scores.csv'

	def foreach(self, fn: Callable[[ICSLine], None]):
		# video,criteria,score,uncertainty
		cmpFile = open(self.file_location, 'r', encoding='utf-8')
		# Skip first line (headers)
		cmpFile.readline()

		while True:
			line = cmpFile.readline()
			# if line is empty, end of file is reached
			if not line:
				break
			fn(ICSLine(line.strip().split(',')))

		cmpFile.close()

	def get_scores(self, criterion:str=None, users:Iterable[str]=None, vids:Iterable[str]=None) -> dict[str,dict[str,dict[str,tuple[float,float]]]]:
		"""

		Args:
			criterion (str, optional): Filter to given criterion only. None means no filtering on criteria.
			users (Iterable[str], optional): List or set of usernames to extract. None means no filtering on users.
			vids (Iterable[str], optional): List of video ids to extract. None means no filtering on videos.

		Returns:
			dict[str,dict[str,dict[str,tuple[float,float]]]]: `(score, uncertainty) = out[user][video][criterion]`
		"""
		data:dict[str,dict[str,dict[str,float]]] = dict()

		def parse_line(line: ICSLine):
			if (not criterion or criterion == line.criterion) \
				and (not users or line.user in users) \
				and (not vids or line.video in vids):
				data.setdefault(line.user, dict()).setdefault(line.video, dict())[line.criterion] = (line.score, line.uncertainty)
		self.foreach(parse_line)
		return data
