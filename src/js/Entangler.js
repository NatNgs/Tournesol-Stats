/**
 * This is the main Javascript file for Tournesol Entangler
 *
 * Here are all functions called by HTML actions (onLoad, buttons, ...), and function to update HTML
 * - Functions interacting with HTML (for example using document.getElementBy##) must not exist outside this JS file
 * - Functions that has no interaction with HTML must be moved to other JS files and imported
 */

const dataset = new DatasetManager()
const HTML_ELMS = {}

function onPageLoad() {
	HTML_ELMS.loading = document.getElementById('loading_status')
	HTML_ELMS.fileInput = document.getElementById('datasetzip')
	HTML_ELMS.userapply = document.getElementById('userapply')
	HTML_ELMS.usernameinpt = document.getElementById('username')
}

let curr_status = null
function setStatus(status_code, status_text) {
	if(status_text) {
		HTML_ELMS.loading.innerText = status_text
	}
	if(status_code && status_code !== curr_status) {
		if(curr_status) {
			HTML_ELMS.loading.classList.remove(curr_status)
		}
		HTML_ELMS.loading.classList.add(status_code)
		curr_status = status_code
	}
	console.debug('Status:', curr_status, '-', HTML_ELMS.loading.innerText)
}

function onSetDatasetZip() {
	const file = HTML_ELMS.fileInput.files[0]
	if(file) {
		HTML_ELMS.fileInput.setAttribute('disabled', 'disabled')
		HTML_ELMS.userapply.setAttribute('disabled', 'disabled')
		setStatus('working')
		dataset.setZip(file, (status) => setStatus(null, status))
		.then(() => {
			HTML_ELMS.fileInput.removeAttribute('disabled')
			HTML_ELMS.userapply.removeAttribute('disabled')
			setStatus('success', 'Dataset loaded successfully. Select a user and Apply to continue')
		})
		.catch((err) => {
			HTML_ELMS.fileInput.removeAttribute('disabled')
			console.error(err)
			setStatus('error', 'Failed to load dataset (' + err + '). Please try again with another file')
			HTML_ELMS.fileInput.value = null
		})
	}
}

let currentSelectedUsername = null
function onApplyUsername() {
	currentSelectedUsername = HTML_ELMS.usernameinpt.value.trim()
	if(!currentSelectedUsername) return // No username set
	if(!Object.keys(dataset.comparisons).length) return // Dataset not loaded yet
	if(!(currentSelectedUsername in dataset.comparisons)) {
		setStatus('error', 'User not found (username is case sensitive)')
		return
	}

	// Compute simple stats & display them
	document.getElementById("stt_nb_videos").innerText = Object.keys(dataset.individualScores[currentSelectedUsername]).length
	document.getElementById("stt_comparisons").innerText = Object.values(dataset.comparisons[currentSelectedUsername]['largely_recommended']).map(w => w.length).reduce((a,b)=>a+b,0)
	document.getElementById("stt_connected_components").innerText = '?'
	document.getElementById('stt_candidates').innerHTML = '?'
	setStatus('success', 'Loaded user data: ' + currentSelectedUsername.replaceAll('<', '&lt;'))
}


function makeSuggestions() {
	setStatus('working', 'Computing user data...')
	const graph = new TnslGraph(dataset)

}

// // // Graph modes

async function showProgressiveFullGraph() {
	if(!dataset || !currentSelectedUsername) {
		return alert("Progressive graph requires to select dataset and a user")
	}
	if(curr_status == 'working') {
		return alert("Please wait for current task, or refresh the page")
	}

	// Show loading
	const graph = new TnslGraph(dataset)

	await new Promise((resolve)=>{
		const weeks = Object.keys(dataset.comparisons[currentSelectedUsername]['largely_recommended'])
		weeks.sort()
		// Add first week links
		let currW = weeks.shift()
		setStatus('working', 'Drawing comparisons... (' + currW + ')')
		for(const c of dataset.comparisons[currentSelectedUsername]['largely_recommended'][currW]) {
			graph.addLink(c.pos, c.neg, c.score/(c.score_max || 10))
		}

		const _updateStats = () => {
			// connected components
			const gm = {}
			graph.data.groups.forEach(g => gm[g.length] = (gm[g.length] || 0) + 1)
			const gs = Object.keys(gm)
			gs.sort((a,b)=>+a<+b?1:-1)
			document.getElementById("stt_connected_components").innerText = gs.map(size=>'' + size +(gm[size] > 1 ? `(x${gm[size]})` : '')).join(', ')
		}
		_updateStats()

		// Add graph viz to viewport
		document.getElementById('graph').innerHTML = ''

		const zone = document.getElementById('graph')
		const _onDrawStart = () => {
			setStatus('working', 'Drawing...')
		}
		const _onEnd = () => {
			if(weeks.length) {
				currW = weeks.shift()
				setStatus('working', 'Optimizing graph... (' + currW + ')')
				for(const c of dataset.comparisons[currentSelectedUsername]['largely_recommended'][currW]) {
					graph.addLink(c.pos, c.neg, c.score/(c.score_max || 10))
				}
				zone.innerHTML = ''
				zone.appendChild(graph.makeD3(_onEnd))

				_updateStats()
				return
			}

			HTML_ELMS.userapply.removeAttribute('disabled')
			HTML_ELMS.usernameinpt.removeAttribute('disabled')
			setStatus('success', 'Drawing complete')

			// Candidates
			_updateStats()
			const suggested = graph.suggestComparisons()
			if(suggested.length)
				document.getElementById('stt_candidates').innerHTML = `<a target="_blank" rel="noopener noreferrer" href="https://tournesol.app/comparison?uidA=yt:${suggested[0][0].id}&uidB=yt:${suggested[0][1].id}">Compare on Tournesol</a>`
			else
				document.getElementById('stt_candidates').innerHTML = 'None'
			console.log(suggested)
		}
		zone.appendChild(graph.makeD3(_onDrawStart,_onEnd))

		setTimeout(resolve)
	})
}

async function showFullGraph() {
	if(!dataset || !currentSelectedUsername) {
		return alert("Full graph requires to select dataset and a user")
	}
	if(curr_status == 'working') {
		return alert("Please wait for current task, or refresh the page")
	}

	// Show loading
	const graph = new TnslGraph(dataset)

	const weeks = Object.keys(dataset.comparisons[currentSelectedUsername]['largely_recommended'])
	weeks.sort()
	// Add first week links
	for(const w of weeks) {
		setStatus('working', 'Computing user data (' + w + ')...')
		await new Promise((resolve)=>{
			for(const c of dataset.comparisons[currentSelectedUsername]['largely_recommended'][w]) {
				graph.addLink(c.pos, c.neg, c.score/(c.score_max || 10))
			}
			setTimeout(resolve)
		})
	}

	await new Promise((resolve)=>{
		// connected components
		const gm = {}
		graph.data.groups.forEach(g => gm[g.length] = (gm[g.length] || 0) + 1)
		const gs = Object.keys(gm)
		gs.sort((a,b)=>+a<+b?1:-1)
		document.getElementById("stt_connected_components").innerText = gs.map(size=>'' + size +(gm[size] > 1 ? `(x${gm[size]})` : '')).join(', ')

		// Add graph viz to viewport
		document.getElementById('graph').innerHTML = ''

		const zone = document.getElementById('graph')
		const _onDrawStart = () => {
			setStatus('working', 'Drawing...')
		}
		const _onEnd = () => {
			HTML_ELMS.userapply.removeAttribute('disabled')
			HTML_ELMS.usernameinpt.removeAttribute('disabled')
			setStatus('success', 'Drawing complete')
		}
		zone.appendChild(graph.makeD3(_onDrawStart, _onEnd))

		// Candidates
		const suggested = graph.suggestComparisons()
		if(suggested.length)
			document.getElementById('stt_candidates').innerHTML = `<a target="_blank" rel="noopener noreferrer" href="https://tournesol.app/comparison?uidA=yt:${suggested[0][0].id}&uidB=yt:${suggested[0][1].id}">Compare on Tournesol</a>`
		else
			document.getElementById('stt_candidates').innerHTML = 'None'
		console.log(suggested)

		setTimeout(resolve)
	})
}
