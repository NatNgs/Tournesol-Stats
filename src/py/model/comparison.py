from model.users import TournesolUser
from model.video import Video

class Comparison:
	def __init__(self, user:TournesolUser, v1:Video, v2:Video):
		self.user = user
		self.v1 = v1
		self.v2 = v2
		self.criteria:dict[str,dict[str,float]] = dict()
