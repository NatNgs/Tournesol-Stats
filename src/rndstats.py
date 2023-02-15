import sys
from model.comparisons import ComparisonFile, ComparisonLine

def get_users_count_stats(cmpFile: ComparisonFile):
	nb_comparisons_by_user: dict[str, dict[str, int]] = dict() # Kind, user, count

	def line_parser(line: ComparisonLine):
		if not line.criteria in nb_comparisons_by_user:
			nb_comparisons_by_user[line.criteria] = dict()

		if not line.user in nb_comparisons_by_user[line.criteria]:
			nb_comparisons_by_user[line.criteria][line.user] = 1
		else:
			nb_comparisons_by_user[line.criteria][line.user] = nb_comparisons_by_user[line.criteria][line.user] + 1

	cmpFile.foreach(line_parser)

	# Aggregate
	nb_comparisons_by_criteria: dict[str, dict[int, int]] = dict() # Criteria, rank (how many comparisons), count (how many users have this many comparisons)
	for criteria in nb_comparisons_by_user:
		nb_comparisons_by_criteria[criteria]: dict[int, int] = dict()
		for count in nb_comparisons_by_user[criteria].values():
			if not count in nb_comparisons_by_criteria[criteria]:
				nb_comparisons_by_criteria[criteria][count] = 1
			else:
				nb_comparisons_by_criteria[criteria][count] = nb_comparisons_by_criteria[criteria][count] + 1


	print()
	for criteria in nb_comparisons_by_criteria:
		print(criteria)
		usercount = len(nb_comparisons_by_user[criteria])

		nbcomp_criteria = nb_comparisons_by_criteria[criteria]
		cumulated_nbcomp = [0]
		m = max(nbcomp_criteria.keys())
		for rnk in range(1, m+1):
			if rnk in nbcomp_criteria:
				cumulated_nbcomp.append(cumulated_nbcomp[-1] + nbcomp_criteria[rnk])
			else:
				cumulated_nbcomp.append(cumulated_nbcomp[-1])

		# Power of 10
		inc = 1
		while inc < m:
			print(f"\t- {cumulated_nbcomp[inc]} users have done {inc} comparisons or less ({cumulated_nbcomp[inc]/usercount:0.1%})")
			inc = inc * 10
		inc = int(inc / 10)
		print(f"\t- {usercount-cumulated_nbcomp[inc]} users have done more than {inc} comparisons ({(usercount-cumulated_nbcomp[inc])/usercount:0.1%})")


		# nbusers = nbcomparisons
		keys = list(nbcomp_criteria.keys())
		keys.sort(reverse=True)
		rnk = 0
		tmp = 0
		while tmp < keys[rnk]:
			tmp = tmp + nbcomp_criteria[keys[rnk]]
			rnk = rnk + 1

		print(f"\t- {tmp} users have done more than {tmp} comparisons ({tmp/usercount:0.1%})")
		print()


if __name__ == '__main__':
	# Unload parameters
	if len(sys.argv) < 2:
		print('ERROR: Missing arguments', file=sys.stderr)
		print(f"""Usage: $ {sys.argv[0]} <dataDir>
	dataDir:
		Directory where the public dataset is located
		(ex: /data/input/tournesol_export_2023mmddThhmmssZ)
""")
		exit(-1)

	input_dir = sys.argv[1]

	cmpFile = ComparisonFile(input_dir)

	get_users_count_stats(cmpFile)

