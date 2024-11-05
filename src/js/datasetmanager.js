function DatasetManager() {
	const THIS = this
	this.zip = null

	this.individualScores = {} // {<user>: {<vid>: {<criterion>: {score: <float>, uncertainty: <float>, voting_right: <float>}}}}
	this.collectiveScores = {} // {<vid>: {<criterion>: {score: <float>, uncertainty: <float>}}}
	this.comparisons = {} // {<user>: {<criterion>: {<week>: [{pos: <vid>, neg: <vid>, score: <float>, score_max: <float>}]}}}

	this.setZip = (file, onUpdate) => {
		var zip = new JSZip()
		onUpdate('Extracting Dataset...')
		return zip.loadAsync(file)
			.then((content) => THIS.zip = content)
			.then(() => onUpdate('Loading collective scores...'))
			.then(THIS.loadCollectiveScores)
			.then(() => onUpdate('Loading individual scores...'))
			.then(THIS.loadIndividualScores)
			.then(() => onUpdate('Loading comparisons...'))
			.then(THIS.loadComparisons)
	}

	this.loadCollectiveScores = () => new Promise((resolve, reject) => {
		const REQ_COLS = ['video', 'criteria', 'score'/*, 'uncertainty'*/]
		const ta = new Date()
		if(!THIS.zip || !THIS.zip.files || !('collective_criteria_scores.csv' in THIS.zip.files)) {
			return reject('No collective_criteria_scores.csv file found in Zip')
		}
		THIS.zip.file('collective_criteria_scores.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			for(const col of REQ_COLS) {
				if(header.indexOf(col) < 0) {
					console.error('collective_criteria_scores.csv format', header)
					return reject('Unexpected collective_criteria_scores.csv file format')
				}
			}

			rows.map(r => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			}).forEach((obj) => {
				if(!(obj.video in THIS.collectiveScores)) {
					THIS.collectiveScores[obj.video] = {}
				}
				if(!(obj.criteria in THIS.collectiveScores[obj.video])) {
					THIS.collectiveScores[obj.video][obj.criteria] = {}
				}
				THIS.collectiveScores[obj.video][obj.criteria] = {
					score: parseFloat(obj.score),
					//uncertainty: parseFloat(obj.uncertainty),
				}
			})
			console.log('Loaded ' + rows.length + ' collective scores in', (new Date()-ta)/1000, 'seconds')
		})
		.then(resolve)
		.catch(reject)
	})

	this.loadIndividualScores = () => new Promise((resolve, reject) => {
		const REQ_COLS = ['public_username', 'video', 'criteria', 'score'/*, 'uncertainty', 'voting_right'*/]
		const ta = new Date()
		THIS.zip.file('individual_criteria_scores.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			for(const col of REQ_COLS) {
				if(header.indexOf(col) < 0) {
					console.error('individual_criteria_scores.csv format', header)
					return reject('Unexpected individual_criteria_scores.csv file format')
				}
			}

			rows.map((r) => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			}).forEach((obj) => {
				if(!(obj.public_username in THIS.individualScores)) {
					THIS.individualScores[obj.public_username] = {}
				}
				if(!(obj.video in THIS.individualScores[obj.public_username])) {
					THIS.individualScores[obj.public_username][obj.video] = {}
				}
				THIS.individualScores[obj.public_username][obj.video][obj.criteria] = {
					score: parseFloat(obj.score),
					//uncertainty: parseFloat(obj.uncertainty),
					//voting_right: parseFloat(obj.voting_right),
				}
			})
			console.log('Loaded ' + rows.length + ' individual scores in', (new Date()-ta)/1000, 'seconds')
		})
		.then(resolve)
		.catch(reject)
	})

	this.loadComparisons = () => new Promise((resolve, reject) => {
		const REQ_COLS = ['public_username', 'video_a', 'video_b', 'criteria', 'score'/*, 'score_max'*/, 'week_date']
		const ta = new Date()
		THIS.zip.file('comparisons.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			for(const col of REQ_COLS) {
				if(header.indexOf(col) < 0) {
					console.error('comparisons.csv format', header)
					return reject('Unexpected comparisons.csv file format')
				}
			}

			rows.map((r) => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			}).forEach((obj) => {
				if(!(obj.public_username in THIS.comparisons)) {
					THIS.comparisons[obj.public_username] = {}
				}
				if(!(obj.criteria in THIS.comparisons[obj.public_username])) {
					THIS.comparisons[obj.public_username][obj.criteria] = {}
				}
				if(!(obj.week_date in THIS.comparisons[obj.public_username][obj.criteria])) {
					THIS.comparisons[obj.public_username][obj.criteria][obj.week_date] = []
				}

				THIS.comparisons[obj.public_username][obj.criteria][obj.week_date].push({
					pos: obj.video_a,
					neg: obj.video_b,
					score: parseFloat(obj.score),
					//score_max: parseFloat(obj.score_max),
				})
			})
			console.log('Loaded ' + rows.length + ' comparisons in', (new Date()-ta)/1000, 'seconds')
		})
		.then(resolve)
		.catch(reject)
	})
}
