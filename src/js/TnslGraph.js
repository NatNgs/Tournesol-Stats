
/**
 * @param {string} id youtube video id
 * @param {number} index numerical id
 * @param {DatasetManager} dataset
 */
function Node(id, index, dataset) {
	this.id = id // youtube video id
	this.index = index // nodes.indexOf(#) == this node
	this.group = -1 // groups.indexOf(#) contains this node
	this.indiv_cmps = [] // list of node objects this one is linked to
	this.distances = {} // distance from this node to others (only contains reachable ones) - nodes in indiv_cmps will have distance=1
	this.distances[id] = 0 // distance to self = 0
	this.dirrected = {} // distance from this node to others in dirrected graph mode (from this node to others only)
	this.dirrected[id] = 0
	this.n_contributors = Object.values(dataset.individualScores).filter(userscores => id in userscores).length // number of public contributors of this video

	// d3js Will set and use following properties: this.x, this.y, this.vx, this.vy
}

/**
 * @param {DatasetManager} dataset
 */
function TnslGraph(dataset) {
	console.log('TnslGraph', this)

	// // // Properties // // //

	this.data = {
		nodes_index: {}, // map node.id => index (for d3js)
		nodes: [], // list of node objects -- WARN: Node.index is the location of the node within this list, sort/pop carefully
		links: [],
		groups: [], // list of groups; every group is a list of node objects
	}
	this.div = null // @see _makeD3

	// // // PUBLIC // // //
	this.addLink = (na_id, nb_id, val) => {
		// nodes
		if(!this.data.nodes_index[na_id] && this.data.nodes_index[na_id] !== 0) {
			// Initiate new node na
			const index = this.data.nodes.length
			this.data.nodes_index[na_id] = index
			this.data.nodes[index] = new Node(na_id, index, dataset)
		}
		const na = this.data.nodes[this.data.nodes_index[na_id]]

		if(!this.data.nodes_index[nb_id] && this.data.nodes_index[nb_id] !== 0) {
			// Initiate new node nb
			const index = this.data.nodes.length
			this.data.nodes_index[nb_id] = index
			this.data.nodes[index] = new Node(nb_id, index, dataset)
		}
		const nb = this.data.nodes[this.data.nodes_index[nb_id]]

		// links
		na.indiv_cmps.push(nb)
		nb.indiv_cmps.push(na)
		if(val >= 0) {
			this.data.links.push({source: na, target: nb, val: val})
			// Update dirrected distances
			for(const nc in nb.dirrected) {
				if(!isFinite(na.dirrected[nc]) || na.dirrected[nc] > nb.dirrected[nc] + 1) {
					na.dirrected[nc] = nb.dirrected[nc] + 1
				}
			}
		}
		if(val <= 0) {
			if(val < 0) this.data.links.push({source: nb, target: na, val: -val})
			// Update dirrected distances
			for(const nc in na.dirrected) {
				if(!isFinite(nb.dirrected[nc]) || nb.dirrected[nc] > na.dirrected[nc] + 1) {
					nb.dirrected[nc] = na.dirrected[nc] + 1
				}
			}
		}

		// groups
		if(na.group < 0 && nb.group < 0) {
			// Create new group
			na.group = this.data.groups.length
			nb.group = na.group
			this.data.groups.push([na, nb])
		} else if(na.group < 0) {
			// Add new node to group
			na.group = nb.group
			this.data.groups[na.group].push(na)
		} else if(nb.group < 0) {
			// Add new node to group
			nb.group = na.group
			this.data.groups[nb.group].push(nb)
		} else if(na.group !== nb.group) {
			// Merge groups
			const g_merge = na.group < nb.group ? na.group : nb.group
			const g_suppr = na.group < nb.group ? nb.group : na.group

			// Update distances of both group members
			for(const sub_na of this.data.groups[na.group]) {
				for(const sub_nb of this.data.groups[nb.group]) {
					// New distance is distance from neigbor_of_na to na + distance from na to nb + distance from nb to neighbor_of_nb
					// distance from na to nb will be 1 as we are currently adding this link
					const d = sub_na.distances[na.id] + 1 + sub_nb.distances[nb.id]
					sub_na.distances[sub_nb.id] = d
					sub_nb.distances[sub_na.id] = d
				}
			}

			// Do merge groups
			for(const n of this.data.groups[g_suppr]) {
				this.data.groups[g_merge].push(n)
				n.group = g_merge
			}
			const last_g = this.data.groups.length-1

			// Remove empty group from groups list
			if(g_suppr < last_g) {
				this.data.groups[g_suppr] = this.data.groups[last_g]
				this.data.groups[last_g].forEach(n => n.group = g_suppr)
			}
			this.data.groups.pop()
		}

		// Update distances to na
		for(const sub_nb_id in nb.distances) {
			const d = nb.distances[sub_nb_id] + 1
			if(!(sub_nb_id in na.distances) || na.distances[sub_nb_id] > d) {
				na.distances[sub_nb_id] = d
				this.data.nodes[this.data.nodes_index[sub_nb_id]].distances[na.id] = d
			}
		}
		// Update distances to nb
		for(const sub_na_id in na.distances) {
			const d = na.distances[sub_na_id] + 1
			if(!(sub_na_id in nb.distances) || nb.distances[sub_na_id] > d) {
				nb.distances[sub_na_id] = d
				this.data.nodes[this.data.nodes_index[sub_na_id]].distances[nb.id] = d
			}
		}

		// Check for error (if triggered, means DEV mistake)
		if(Object.values(na.distances).length < this.data.groups[na.group].length || Object.values(nb.distances).length < this.data.groups[nb.group].length) {
			console.log(na, nb, this.data.groups[na.group])
			throw '!!! Distances - Group mismatch !!!'
		}
	}

	this.dirDistanceBetween = (n1, n2) => {
		if(n1 === n2) return 0
		n21 = n2.dirrected[n1.id]
		n12 = n1.dirrected[n2.id]
		return isFinite(n12) && isFinite(n21)
			? (n12 > n21 ? n21 : n12)
				: isFinite(n12) ? n12
					: isFinite(n21) ? n21
						: -1
	}

	// TODO: To be improved: Consider previous suggestions as existing links for next suggestions
	this.suggestComparisons = () => {
		const candidates = []
		// Add in candidates, every node that:
		// - have less comparisons (node.indiv_cmps.length) than public contributors (node.n_contributors)
		// - [TODO] AND have any comparison since last year
		for(const node of this.data.nodes) {
			if(node.indiv_cmps.length < node.n_contributors) {
				candidates.push(node)
			}
		}

		// Sort them by their avg_dist
		const avg_dists = {}
		candidates.forEach(n => avg_dists[n.id] = _getNodeAvgDist(n))
		candidates.sort((a,b) => avg_dists[a]>avg_dists[b]?1:-1)

		const suggestions = []
		// Make comparisons suggestions
		while(candidates.length > 1) {
			// Pick first candidate
			const picked = candidates.shift()

			// Keep from candidates, vids not present in picked directed graph
			const against = candidates.filter(c => this.dirDistanceBetween(picked, c) < 0)

			// Compute max distance from picked to other candidates
			const maxD = against.map(c => c.distances[picked.id]).reduce((d,max)=>d>max?d:max,3) // Min distance to recom = 3
			const remaining = against.filter(c => !isFinite(c.distances[picked.id]) || c.distances[picked.id] >= maxD)
			if(!remaining.length) continue // No pair available, skip

			// Take the first one in candidates list order
			const pair = remaining[0]
			candidates.splice(candidates.indexOf(pair),1)

			// Make a comparison from them both
			suggestions.push([picked, pair])
		}

		return suggestions
	}

	// TODO: Make nodes draggable (fix node currently being picked, and resume graph computation while dragging)
	this.makeD3 = (onend) => {
		// Select largest connected component
		const nodes = this.data.groups[0]

		// Compute nodes average distances
		const avg_dists = {}
		nodes.forEach(n => avg_dists[n.id] = _getNodeAvgDist(n))

		// Init nodes location, as a spiral from most central to least central
		nodes.sort((a,b) => avg_dists[a]>avg_dists[b]?1:-1)
		nodes.forEach((n,i) => {
			// optiR = Distance relative to average proximity to other nodes
			n.optiR = (avg_dists[n.id]-1) * Math.sqrt(nodes.length)
			if(n.x && n.y) return

			// TODO: Check if node have link to other nodes already having x & y set; if so, set this node location to the average of them

			// Set node location near 0,0, with random angle and radius = optiR
			let ang = i*n.optiR
			n.x = n.optiR * Math.cos(ang)
			n.y = n.optiR * Math.sin(ang)
			n.vx = 0
			n.vy = 0
		})

		// Create a simulation with several forces
		const optimDist = Math.sqrt(d3.max(nodes.map(n => n.indiv_cmps.length)))
		const simulation = d3.forceSimulation(nodes)
			.alphaDecay(1/Math.sqrt(nodes.length))
			//.alphaTarget(0.3)
			.velocityDecay(0.01)
			.force('magnet_repulse', d3.forceManyBody().distanceMax(optimDist * Math.sqrt(nodes.length))) // Repulse nodes away from eachother - Disable when "fix_radius" is enabled
			.force('attract_comparisons', d3.forceLink(this.data.links)
				.id(d => d.id)
				.distance(optimDist)
				//.strength((link) => (link.val ? Math.abs(link.val) : 10)/10)
			)
			.force('drag', () => {
				// Apply drag only if node if moving towards outside of the graph
				nodes.filter(n=>Math.abs(n.vx) > 1).forEach(n => n.vx *= .8)//Math.sign(n.vx) * Math.sqrt(Math.abs(n.vx)))
				nodes.filter(n=>Math.abs(n.vy) > 1).forEach(n => n.vy *= .8)//Math.sign(n.vy) * Math.sqrt(Math.abs(n.vy)))
			})
			/*.force('fix_radius', () => {
				// Force nodes distance to the center to be linked to their proximity to other nodes
				nodes.forEach(n => {
					const ang = Math.atan2(n.y, n.x)
					n.x = (n.x*9 + n.optiR*Math.cos(ang))/10
					n.y = (n.y*9 + n.optiR*Math.sin(ang))/10
				})
			})*/
			.force('recenter', () => {
				// Center of gravity of the graph = Center of the viewport
				const _nds = nodes.filter(n => (n.x || n.y) && (n.vx || n.vy))
				let mid = [0,0,0,0]
				_nds.forEach(n => {
					mid[0] += n.x
					mid[1] += n.y
					mid[2] += n.vx
					mid[3] += n.vy
				})
				mid = mid.map(m => m/_nds.length)
				_nds.forEach(n => {
					n.x -= mid[0]
					n.y -= mid[1]
					n.vx -= mid[2]
					n.vx -= mid[3]
				})
			})

		// Create div
		const svg = d3.create("svg").attr("viewBox", [-100, -100, 200, 200])

		// Add a line for each link, and a circle for each node.
		const g_links = svg.append("g")
			.attr("stroke", "#888")
			//.attr("stroke-opacity", 0.5)
			.selectAll("line")
			.data(this.data.links)
			.join("line")

		const g_nodes = svg.append("g")
			.selectAll("circle")
			.data(nodes)
			.join("circle")
			.attr("r", d => d.indiv_cmps.length)
			.attr("fill", _d3_node_colors(avg_dists))

		// Set the position attributes of links and nodes each time the simulation ticks.
		simulation.on("tick", () => {
			g_links
				.attr("x1", d => d.source.x)
				.attr("y1", d => d.source.y)
				.attr("x2", d => d.target.x)
				.attr("y2", d => d.target.y)

			let mm = [0, 0, 0, 0]
			g_nodes
				.attr("cx", d => {
					if(d.x < mm[0]) mm[0] = d.x
					if(d.x > mm[2]) mm[2] = d.x
					return d.x
				})
				.attr("cy", d => {
					if(d.y < mm[1]) mm[1] = d.y
					if(d.y > mm[3]) mm[3] = d.y
					return d.y
				})

			// Auto zoom on content
			if(mm[2]-mm[0] > mm[3]-mm[1]) {
				const r = ((mm[2]-mm[0]) - (mm[3]-mm[1])) /2
				mm[1] -= r
				mm[3] += r
			} else {
				const r = ((mm[3]-mm[1]) - (mm[2]-mm[0])) /2
				mm[0] -= r
				mm[2] += r
			}
			svg.attr("viewBox", [mm[0], mm[1], mm[2]-mm[0], mm[3]-mm[1]])
		})

		this.div = svg.node()
		if(onend) simulation.on("end", onend)
		return this.div
	}

	// // // PRIVATE // // //

	const _getNodeAvgDist = (node) => {
		/**
		 * @returns Average distance to every reachable node
		 */
		return Object.values(node.distances).reduce((a,b)=>a+b, 0) / (this.data.nodes.length - 1)
	}
	const _d3_node_colors = (map) => {
		const range = Object.values(map)
		range.sort((a,b)=>a-b>0?1:-1)
		const q0 = range[0]
		const q1 = range[(range.length/4)|0]
		const q2 = range[(range.length/2)|0]
		const q3 = range[(range.length*3/4)|0]
		const q4 = range[range.length-1]
		console.debug('Colorscale:', [q0,q1,q2,q3,q4])
		const _to_color = d3.scaleLinear().domain([q0,q1,q2,q3,q4]).range(['#664400', '#EEAA22', '#088000', '#0FCC00', '#11ddff'])
		return (n) => _to_color(map[n.id])
	}
}
