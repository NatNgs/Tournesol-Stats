class ComparisonFile:
	def __init__(self, source):
		self.file_location = source + '/comparisons.csv'

	def foreach(self, fn: function[list[str]]):
			# public_username,video_a,video_b,criteria,weight,score
			cmpFile = open(self.file_location, 'r', encoding='utf-8')
			# Skip first line (headers)
			cmpFile.readline()

			while True:
				line = cmpFile.readline()
				# if line is empty, end of file is reached
				if not line:
					return
				fn(line.split(','))
