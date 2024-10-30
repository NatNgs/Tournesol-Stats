
function TnslGraph() {
	console.log(this)

	// // // Properties // // //

	this.data = {
		nodes_index: {},
		nodes: [],
		links: [],
		groups: [],
	}
	this.div = null // @see _makeD3

	// // // PUBLIC // // //
	this.addLink = (nodea, nodeb) => {
		// nodes
		if(!this.data.nodes_index[nodea] && this.data.nodes_index[nodea] !== 0) {
			const index = this.data.nodes.length
			this.data.nodes_index[nodea] = index
			this.data.nodes[index] = {id: nodea, index:index, group: -1, indiv_cmps:[]}
		}
		const na = this.data.nodes[this.data.nodes_index[nodea]]

		if(!this.data.nodes_index[nodeb] && this.data.nodes_index[nodeb] !== 0) {
			const index = this.data.nodes.length
			this.data.nodes_index[nodeb] = index
			this.data.nodes[index] = {id: nodeb, index:index, group: -1, indiv_cmps:[]}
		}
		const nb = this.data.nodes[this.data.nodes_index[nodeb]]

		// links
		this.data.links.push({source: na, target: nb})
		na.indiv_cmps.push(nb)
		nb.indiv_cmps.push(na)

		// groups
		if(na.group < 0 && nb.group < 0) {
			// Create new group
			na.group = this.data.groups.length
			nb.group = this.data.groups.length
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
			for(const n of this.data.groups[g_suppr]) {
				this.data.groups[g_merge].push(n)
				n.group = g_merge
			}
			const last_g = this.data.groups.length-1
			if(g_suppr < last_g) {
				// Remove empty group from groups list
				this.data.groups[g_suppr] = this.data.groups[last_g]
				this.data.groups[last_g].forEach(n => n.group = g_suppr)
			}
			this.data.groups.pop()
		}
	}

	let div = null
	this.getDiv = (onend) => {
		if(div === null) {
			div = _makeD3(onend)
		}
		return div
	}
	// // // PRIVATE // // //

	const _computeCentralities = (group) => {
		// Helper function to perform BFS and calculate distances

		group.map((startNode) => {
			const queue = [startNode];
			const distances = {};
			distances[startNode.id] = 0; // Distance to itself is 0

			let dist_sum = 0;
			while (queue.length) {
				const currentNode = queue.shift();
				const currentDistance = distances[currentNode.id];

				// Iterate over neighbors
				for (let neighbor of currentNode.indiv_cmps) {
					if (!(neighbor.id in distances)) { // If neighbor hasn't been visited
						distances[neighbor.id] = currentDistance + 1 // Set distance
						queue.push(neighbor)
						dist_sum += currentDistance + 1
					}
				}
			}

			startNode.centrality = dist_sum/(group.length-1);
		})
	}

	const _makeD3 = (onend) => {
		// Select largest connected component
		const nodes = this.data.groups[0]

		// Specify the color scale.
		const _colrscale = (range) => {
			range.sort((a,b)=>a-b>0?1:-1)
			const q0 = range[0]
			const q1 = range[(range.length/4)|0]
			const q2 = range[(range.length/2)|0]
			const q3 = range[(range.length*3/4)|0]
			const q4 = range[range.length-1]
			console.log('Colorscale:', [q0,q1,q2,q3,q4])
			return d3.scaleLinear().domain([q0,q1,q2,q3,q4]).range(['#664400', '#EEAA22', '#088000', '#0FCC00', '#11ddff'])
		}

		_computeCentralities(nodes)
		const color = _colrscale(nodes.map(n => n.centrality))
		const node_color = (d) => color(d.centrality)

		// Create a simulation with several forces
		const simulation = d3.forceSimulation(nodes)
			.alphaDecay(0.005)
			.velocityDecay(0)
			.force('magnet_repulse', d3.forceManyBody())
			.force('attract_comparisons', d3.forceLink(this.data.links).id(d => d.id).distance(d3.max(nodes.map(n => n.indiv_cmps.length))))
			.force('drag', () => {
				nodes.filter(n=>Math.abs(n.vx) > 1).forEach(n => n.vx = Math.sign(n.vx) * Math.sqrt(Math.abs(n.vx)))
				nodes.filter(n=>Math.abs(n.vy) > 1).forEach(n => n.vy = Math.sign(n.vy) * Math.sqrt(Math.abs(n.vy)))
			})
			.force('recenter', () => {
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
			.attr("stroke-opacity", 0.5)
			.selectAll("line")
			.data(this.data.links)
			.join("line")

		const g_nodes = svg.append("g")
			.selectAll("circle")
			.data(nodes)
			.join("circle")
			.attr("r", d => d.indiv_cmps.length)
			.attr("fill", node_color)

		// Set the position attributes of links and nodes each time the simulation ticks.
		simulation.on("tick", () => {
			g_links
				.attr("x1", d => d.source.x)
				.attr("y1", d => d.source.y)
				.attr("x2", d => d.target.x)
				.attr("y2", d => d.target.y)

			let mm = 0
			g_nodes
				.attr("cx", d => {
					if(d.x > mm) mm = d.x
					if(d.x < -mm) mm = -d.x
					return d.x
				})
				.attr("cy", d => {
					if(d.y > mm) mm = d.y
					if(d.y < -mm) mm = -d.y
					return d.y
				})

			// Auto zoom on content
			svg.attr("viewBox", [-mm, -mm, 2*mm, 2*mm])
		})

		if(onend) simulation.on("end", onend)

		return svg.node()
	}
}
