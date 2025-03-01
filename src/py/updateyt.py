import argparse

from model.tournesol_dataset.collectivecriteriascores import CollectiveCriteriaScoresFile
from dao.youtube_api import YTData


################
##### MAIN #####
################


# Unload parameters
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--tournesoldataset', help='Directory where the public dataset is located', default='data/tournesol_dataset', type=str)
parser.add_argument('-c', '--cache', help='Youtube data cache file location', default='data/YTData_cache.json.gz', type=str)

args = vars(parser.parse_args())

CCSF = CollectiveCriteriaScoresFile(args['tournesoldataset'])

YTDATA = YTData()
try:
	YTDATA.load(args['cache'])
except FileNotFoundError:
	pass

vids = CCSF.get_scores('largely_recommended').keys()

# YT Update: Import new videos
YTDATA.update(vids, force=False, save=args['cache'])

# Tournesol Update
YTDATA.updateTournesol(save=args['cache'], cachedDays=31*3)
