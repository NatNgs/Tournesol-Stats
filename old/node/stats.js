// Execiton: node stats.js datafolder
var fs = require('fs')

function main() {
	// Read input file
	const datafolder = process.argv[2]
	const filterUser = process.argv[3] || null

	fs.readFile(datafolder + '/comparisons.csv', 'utf-8', (err, filecontent) => {
		if(err) {
			console.log(process.argv);
			throw err;
		}
		const data = readComparisonsFile(filecontent)
		filecontent = undefined

		findLinksBetweenVideos(data, userVids(data, filterUser))
	});
}

function readComparisonsFile(filecontent) {
	console.log('Parsing file...')
	const lines = filecontent.split(/\r?\n/).filter(l=>l.trim()).map(l=>l.split(','))
	lines.shift()

	const data = []
	for(const line of lines) {
		const s = +line[5]

		data.push({
			u: line[0],
			vp: (s < 0) ? line[2] : line[1],
			vm: (s < 0) ? line[1] : line[2],
			c: line[3],
			//w: +line[4],
			s: s < 0 ? -s : s
		})
	}

	console.log('Parsed', data.length, 'lines\n')
	return data
}

function userVids(data, user) {
	if(!user) return null;

	const uVids = {}
	for(const line of data) {
		if(line.u === user) {
			uVids[line.vp] = true
			uVids[line.vm] = true
		}
	}
	console.log(user, 'has compared', Object.keys(uVids).length, 'videos')
	return uVids
}

function groupByLink(directLinks) {
	const ungroupped = Object.values(directLinks)

	// Finding groups
	const groups = [] // [ [vid1, vid2, ...], [vid3, vid4, ...], ...]
	while(ungroupped.length) {
		const l1 = ungroupped.shift()
		const newgroup = Object.values(l1)

		for(let i=0; i<newgroup.length; i++) {
			const vid = newgroup[i]
			// find all ungroupped links having vid
			for(let j=ungroupped.length-1; j>=0; j--) {
				if(ungroupped[j][0] === vid) {
					if(newgroup.indexOf(ungroupped[j][1]) < 0) {
						newgroup.push(ungroupped[j][1])
					}
				} else if(ungroupped[j][1] === vid) {
					if(newgroup.indexOf(ungroupped[j][0]) < 0) {
						newgroup.push(ungroupped[j][0])
					}
				} else {
					continue
				}

				// pop from ungroupped list
				ungroupped[j] = ungroupped[ungroupped.length-1]
				ungroupped.length --
			}
		}
		// add group
		groups.push(newgroup)
	}

	groups.sort((a,b)=>(a.length > b.length ? 1 : a.length < b.length ? -1 : 0))
	return groups
}
function evaluateGroup(vids, links, filterVids) {
	console.log('Evaluating group of', vids.length, 'vids &', links.length, 'connections...')

	// Build link graph
	const graph = {} // {vid1: [vid2, ...], ...}
	while(links.length) {
		const link = links.shift()
		;(graph[link[0]] ||= []).push(link[1])
		;(graph[link[1]] ||= []).push(link[0])
	}
	links = undefined // DESTRUCTED

	vids.sort((a,b)=>Math.sign(graph[b].length - graph[a].length))
	console.log('Max node connections (distance = 1):', graph[vids[0]].length)

	const outStats = []
	for(let i1=vids.length-1; i1>=0; i1--) {
		const vid1 = vids[i1]
		if(filterVids && !(vid1 in filterVids)) continue

		// Compute all distances >1 from vid1
		const dists = [graph[vid1]]
		const found = {vid1:true} // add self to found (we know distance to self = 0)
		for(const v of graph[vid1]) {
			found[v] = true // add all direct connections (already known)
		}
		let founds = Object.keys(found).length

		// distance: 0=next to each other, 1= 1 intermediate, ...
		for(let distance=0; distance < dists.length && founds < vids.length; distance++) {
			dists[distance+1] ||= []
			for(let i2=dists[distance].length-1; i2>=0; i2--) {
				const vid2 = dists[distance][i2]
				const g2 = graph[vid2]
				for(let i3=g2.length-1; i3>=0; i3--) {
					const vid3 = g2[i3]
					if(!(vid3 in found)) {
						founds++
						found[vid3] = true
						dists[distance+1].push(vid3)
					}
				}
			}
		}

		const lengths = Object.values(dists).map(a=>a.length)
		const stt = {
			v: vid1, // vid
			l: lengths, // lengths
			o: dists[dists.length-1], // opposites
			a: 1+lengths.reduce((prev,curr,index)=>prev + curr*index, 0) / (vids.length-1) // Average distance to elements
		}
		outStats.push(stt)

		// Print
		if(i1%500 === 0) {
			console.log(vids.length - i1, '/', vids.length, '=>', stt.v, 'avg:', +stt.a.toFixed(2), stt.l.join('-'), '#', (process.memoryUsage().heapUsed / (1024*1024)|0), 'MB')
		}
	}

	console.log('\n')
	return outStats
}
function findLinksBetweenVideos(data, filterVids) {
	console.log('Computing direct links...')
	let directLinks = {} // {vid1_vid2=1, vid3_vid4=1, ...}
	for(const line of data) {
		directLinks[(line.vp < line.vm ? line.vp : line.vm) + '\t' + (line.vp < line.vm ? line.vm : line.vp)] = 1
	}
	directLinks = Object.keys(directLinks).map(v=>v.split('\t')) // [ [vid1, vid2], ...]
	console.log(directLinks.length, 'direct links.\n')

	console.log('Grouping Links...')
	const groups = groupByLink(directLinks)
	console.log(groups.length, 'distinct unlinked groups\n')

	// Evaluating biggest group
	const g1 = groups.pop()
	const groupStats = evaluateGroup(g1, directLinks.filter(l=>g1.indexOf(l[0])>=0), filterVids)
	/* groupStats: {
		v: node
		a: avg dist to other nodes
		b: dist to max nodes
		l: dist to furthest nodes
		o: furthest nodes vid id
		d: number of direct connections
	} */
	groupStats.sort((a,b)=>(a.a > b.a ? 1 : -1))

	console.log('\n')
	console.log('Furthest nodes in biggest group:')
	const ggids = groupStats.map(gg=>gg.v)
	for(let i=1; i<=5; i++) {
		const gg = groupStats[groupStats.length-i]
		console.log(gg.v, '=> comparedTo:', gg.l[0], '/ avgDist:', +gg.a.toFixed(2), '/ oppositeNodes: dist =', gg.l.length, gg.o.sort((a,b)=>Math.sign(ggids.indexOf(b) - ggids.indexOf(a))))
	}

	console.log('\nNodes not attached to biggest group:')

	let prt = groups.filter(g=>g.length > 2)
	if(filterVids) {
		prt = prt.filter(v=>v in filterVids)
	}
	console.log(prt.map(g=>g.join(', ')).reverse().join(', ') || 'none')
}

function indexOfMax(arr) {
	if (arr.length === 0) {
		return -1;
	}

	let maxIndex = arr.length-1;
	let max = arr[maxIndex];

	for (var i = maxIndex-1; i >= 0; i--) {
		if (arr[i] > max) {
			maxIndex = i;
			max = arr[i];
		}
	}

	return maxIndex;
}

main();
