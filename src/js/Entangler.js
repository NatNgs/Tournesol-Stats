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

function onApplyUsername() {
	const selectedUsername = HTML_ELMS.usernameinpt.value.trim()
	if(!selectedUsername) return // No username set
	if(!Object.keys(dataset.comparisons).length) return // Dataset not loaded yet
	if(!(selectedUsername in dataset.comparisons)) {
		setStatus('error', 'User not found (username is case sensitive)')
		return
	}

	// Show loading
	setStatus('working', 'Computing user data...')
	HTML_ELMS.userapply.setAttribute('disabled', 'disabled')
	HTML_ELMS.usernameinpt.setAttribute('disabled', 'disabled')

	// Prepare graph
	setTimeout(() => {
		const graph = new TnslGraph(dataset)

		for(const w in dataset.comparisons[selectedUsername]['largely_recommended']) {
			for(const c of dataset.comparisons[selectedUsername]['largely_recommended'][w]) {
				graph.addLink(c.pos, c.neg)
			}
		}

		// Update stats
		document.getElementById("stt_nb_videos").innerText = Object.keys(dataset.individualScores[selectedUsername]).length
		document.getElementById("stt_comparisons").innerText = graph.data.links.length

		// connected components
		const gm = {}
		graph.data.groups.forEach(g => gm[g.length] = (gm[g.length] || 0) + 1)
		const gs = Object.keys(gm)
		gs.sort((a,b)=>+a<+b?1:-1)
		document.getElementById("stt_connected_components").innerText = gs.map(size=>'' + size +(gm[size] > 1 ? `(x${gm[size]})` : '')).join(', ')

		// Candidates (WIP)
		const candidates = graph.suggestComparison()
		document.getElementById('stt_candidates').innerHTML = candidates.length

		// Add graph viz to viewport
		document.getElementById('graph').innerHTML = ''
		setStatus('working', 'Optimizing graph...')
		document.getElementById('graph').appendChild(graph.getDiv(() => {
			HTML_ELMS.userapply.removeAttribute('disabled')
			HTML_ELMS.usernameinpt.removeAttribute('disabled')
			setStatus('success', 'Drawing complete')
		}))
	})
}
