
import os
import re
import time


def optimize(optimized_file: str):
	print('Optimizing SVG...')
	start = time.time()

	# Rename unoptimized file
	unoptimized_file = optimized_file + '.tmp'
	try:
		os.rename(optimized_file, unoptimized_file)
	except Exception:
		print(f"Could not rename {optimized_file} to {unoptimized_file} - Cancel optimization")
		return

	try:
		unopt_size = os.path.getsize(unoptimized_file)
		unoptimized = open(unoptimized_file, 'r')
		optimized = open(optimized_file, 'w')

		writingline = ''
		for i,line in enumerate(unoptimized):
			if i <= 3:
				optimized.write(line)
				continue

			writingline += line.strip(' \n\t')
			if writingline.endswith('>'):
				writingline = writingline.replace(' -', '-')
				writingline = re.sub(r'rotate\(-?0[, °][^()]+\)', '', writingline)
				writingline = re.sub(r'fill: *none; *', '', writingline)
				writingline = re.sub(r' [^ =]+=" *"', '', writingline)
				writingline = re.sub(r'(\.[0-9]{2})[0-9]+', r'\1', writingline)
				writingline = re.sub(r' *: *', ':', writingline)
				writingline = writingline.replace('id="LineCollection_1"', 'id="LineCollection_1" fill="none"')

				# Lines
				linestyle = re.search(r'style=" *((?:[^ :"]+ *: *[^" ;]+ *;* *)+)"', writingline)
				if linestyle:
					keyval = re.split(r'[ :;]+', linestyle.group(1))
					newlinestyle = ''
					for k in range(0, len(keyval), 2):
						newlinestyle += f'{keyval[k]}="{keyval[k+1]}" '
					newlinestyle.strip()
					writingline.replace(linestyle.group(), newlinestyle)

				# Circles
				circlepath = re.search(r'M( *[0-9.]+){2} *(C( *[0-9.]+){6}){8} *z', writingline)
				if circlepath:
					vals = re.split(r'[^0-9.]+', circlepath.group())[1:-1]

					xx = [float(vals[x]) for x in range(0,len(vals),2)]
					yy = [float(vals[y]) for y in range(1,len(vals),2)]
					cx = (max(xx)+min(xx))/2
					cy = (max(yy)+min(yy))/2
					r =  (max(xx)-min(xx))/2

					writingline = re.sub(r'<path d="[^"]+"', f'<circle cx="{cx:0.2f}" cy="{cy:0.2f}" r="{r:0.2f}"', writingline)

				optimized.write(writingline)
				optimized.write('\n')
				writingline = ''

		unoptimized.close()
		optimized.flush()
		optimized.close()
		opt_size = os.path.getsize(optimized_file)
		end = time.time()
		print(f"Optimized from {float(unopt_size)/(1024*1024):0.2f}MiB to {float(opt_size)/(1024*1024):0.2f}MiB ({1-opt_size/unopt_size:0.2%} reduction) in {end-start:0.2f}s")
		os.remove(unoptimized_file)
	except Exception as e:
		print(e)
		print()
		print('Cancelling optimization')
		os.remove(optimized_file)
		os.rename(unoptimized_file, optimized_file)
