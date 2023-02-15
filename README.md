# Tournesol-Stats
A collection of tools to visualize and explore the tournesol.app public dataset.

Open source project: feel free to reuse any part (more details in LICENSE.txt)

## Graphing tool

Create a graph, as a .png file, representing the user's comparisons.

- Videos are vertices
	- Color depends on language (colors are ranomly selected)
	- Size depends on number of comparisons made with it
- Comparisons are edges
	- Black edges are comparisons set by the given user
	- Gray edges are comparisons set by other users (wider depending on how many users did the comparison)
	- Green edges are recommended comparisons between seen videos

### Setup

#### Initiate folder structure

The app will work on a specific directory you may need to create empty first:

```
- README.md (this file, for comparison)
- data (directory to create)
	|- YT_API_KEY.txt (see API key configuration below)
	|- cache (directory to create, where youtube data will be cached)
	|- output (directory to create, where output png pictures will be dropped)
```

#### API Key configuration
Create a file in `TournesolStats/data/YT_API_KEY.txt`, and paste your youtube API key in (TODO: document how to find the YT API key)

(For comparison, this readme you're reading is: `TournesolStats/README.md`)

For information, API consumption is low, and will cache all collected data (maximum is 1 request for every 50 video the user (parameter) compared)

#### Tournesol Data
In the footer of [tournesol.app] website, there is a link to download the public dataset.

Get the dataset (downloaded as a zip archive), and unzip-it anywhere you like on your computer.

Keep the directory name (`tournesol_export_yyyymmddThhmmssZ`) and structure inside it unchanged, this script depends on it.


### How to use

`py src/main.py <public-dataset-dir> <user>`

Example:
`py src/main.py ~/downloads/tournesol_export_20001231T235959Z NatNgs`

Will generate the output png file as `TournesolStats/data/output/graph_<username>_<date>.png` (e.g. `graph_NatNgs_20001231.png`)

### Known Limitations

- May not work as intended, or produce an unreadable picture for users with "not enough" or "too much" comparisons done (depends on your appreciation)
- I expect it to take a longer time to compute for users with huge number of comparisons
	- Some benchmarks:
		- User with 80 videos & 150 comparisons: ~4s
		- User with 2000 videos & 5000 comparisons: ~15s
- Not supporting emojis and some symbols (will print squares instead) - may depend on your computer/execution environment
- Non-perfect Recommendations: Does not take into account videos that have not been compared by the selected user
	- A step of the algorithm computes the shortest distance between nodes, and result may be different with full dataset
- No Unit test => May contain bugs
