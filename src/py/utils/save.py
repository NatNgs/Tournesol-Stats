import os
import json
import gzip
from pathlib import Path
from utils.DelayedKeyboardInterrupt import DelayedKeyboardInterrupt


def load_json_gz(filename:str) -> any:
	path = os.path.abspath(filename)
	def opn(f:str):
		with (gzip.open(f, 'rt', encoding='UTF-8')
				if f.endswith('.gz')
				else open(f, 'r', encoding='UTF-8')
		) as file:
			loaded = json.load(file)
			print('Loaded file', os.path.realpath(file.name))
			return loaded

	# Open the given file if exists
	if Path(path).is_file():
		return opn(path)

	# File does not exist. Try open same file with .gz ext (or without .gz ext)
	ungz = path[:-3] if path.endswith('.gz') else (path + '.gz')
	if Path(ungz).is_file():
		return opn(ungz)

	# No file found with that name
	raise FileNotFoundError(f"Neither {path} nor {ungz} files exists")

def save_json_gz(filename:str, data:any) -> str:
	path = os.path.abspath(filename)
	with DelayedKeyboardInterrupt():
		with (gzip.open(path, 'wt', encoding='UTF-8')
				if path.endswith('.gz')
				else open(path, 'w', encoding='UTF-8')
		) as file:
			json.dump(
				data,
				file,
				separators=(',',':'),
				ensure_ascii=True
			)
			return os.path.realpath(file.name)
	return None
