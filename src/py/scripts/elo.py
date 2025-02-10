import math

# eloA: rating of player A
# eloB: rating of player B
# Return probability for player A to win agains player B
def scoreToProba(eloA, eloB):
	return 1 / (1 + math.pow(10, (eloB - eloA) / 400))


# Function to calculate new Elo rating
# d determines whether Player A wins or Player B.
# If K is positive: Player a wins (and uses K as change factor)
# If K is negative: Player b wins (and uses -K as change factor)
def updateEloRating(Ra, Rb, K):
	# Winning probability of Player B
	Pb = scoreToProba(Rb, Ra)
	if K > 0:
		Ra = Ra + K * Pb
		Rb = Rb - K * Pb
	else:
		Ra = Ra + K * (1-Pb)
		Rb = Rb - K * (1-Pb)
	return (Ra, Rb)


# proba: (float from 0 to 1 Exclusive) probability of player A winning (float from 0 to 1 EXCLUSIVE)
# sum: sum of eloA and eloB
# Return eloA and eloB such as ScoreToProba(eloA, eloB) = proba
def probaToScore(proba, sum):
	eloB = (math.log10(1/proba-1)*400+sum)/2
	return (sum-eloB, eloB)

# Function to calculate new Elo rating
# eloA: current elo rating of player A
# eloB: current elo rating of player B
# outcome: actual match result (-1: player B win 100%, 0: draw, 1: player A win 100%)
# factor: float between 0 and 1 (EXCLUSIVE), score update speed (higher: scores update more)
def updateRating(eloA, eloB, outcome, factor):
	currentProba = scoreToProba(eloA, eloB)
	ratio = (outcome+1)/2
	newProba = ratio*factor + currentProba*(1-factor)
	try:
		return probaToScore(newProba, eloA+eloB)
	except ValueError as e:
		print('##ERROR##', eloA, eloB, outcome, factor, currentProba, ratio, newProba)
