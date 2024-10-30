

const NO_CB = (() => {})

function DatasetManager() {
	const THIS = this
	this.zip = null

	this.individualScores = []
	this.collectiveScores = []
	this.comparisons = []
	this.loadedUser =

	this.setZip = (file, cb) => {
		var zip = new JSZip()
		zip.loadAsync(file)
			.then((content) => {
				THIS.zip = content
				THIS.loadCollectiveScores(cb || NO_CB)
			},
			() => cb(false)
		)
	}

	this.loadUserData = (user, cb) => {
		if(!user || !this.zip) {
			cb(false)
		}
		const next = () => {
			if(this.loadedUser !== user || !this.comparisons.length) {
				this.loadUserComparisons(user, ()=>{
					cb(true)
				})
			} else {
				cb(true)
			}
		}
		if(this.loadedUser !== user || !this.individualScores.length) {
			this.loadIndividualScores(user, next)
		} else {
			next()
		}

	}

	this.loadCollectiveScores = (cb) => {
		const ta = new Date()
		if(!THIS.zip || !THIS.zip.files || !('collective_criteria_scores.csv' in THIS.zip.files)) {
			return cb(false)
		}
		THIS.zip.file('collective_criteria_scores.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			if(header.indexOf('video') < 0 || header.indexOf('criteria') < 0 || header.indexOf('score') < 0) {
				console.error('Unexpected file format', header)
			}

			THIS.collectiveScores = rows.map((r) => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			})
			console.log('Loaded ' + THIS.collectiveScores.length + ' collective scores in', (new Date()-ta)/1000, 'seconds')
			if(cb) cb(true);
		}).catch(() => cb && cb(false))
	}

	this.loadIndividualScores = (user, cb) => {
		const ta = new Date()
		THIS.zip.file('individual_criteria_scores.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			if(header.indexOf('public_username') < 0 || header.indexOf('video') < 0 || header.indexOf('criteria') < 0 || header.indexOf('score') < 0) {
				console.error('Unexpected file format', header)
			}

			THIS.individualScores = rows.map((r) => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			}).filter(r => r.public_username == user)
			console.log('Loaded ' + THIS.individualScores.length + ' individual scores in', (new Date()-ta)/1000, 'seconds')
			if(cb) cb(THIS.individualScores);
		})
	}

	this.loadUserComparisons = (user, cb) => {
		const ta = new Date()
		THIS.zip.file('comparisons.csv').async('string').then(csvText => {
			// Séparer les lignes par le retour à la ligne
			const rows = csvText.trim().split('\n')

			// Extraire l'en-tête (la première ligne)
			const header = rows.shift().split(',').map(item => item.trim())

			// Validate format
			if(header.indexOf('public_username') < 0 || header.indexOf('video_a') < 0 || header.indexOf('video_b') < 0 || header.indexOf('criteria') < 0) {
				console.error('Unexpected file format', header)
				alert("Wrong file selected. tournesol_dataset/comparisons.csv expected.")
			}

			THIS.comparisons = rows.map((r) => {
				const values = r.split(',')
				const obj = {}
				for(const col in header) {
					obj[header[col]] = values[col].trim()
				}
				return obj
			}).filter(r => r.public_username == user)
			console.log('Loaded ' + THIS.comparisons.length + ' comparisons in', (new Date()-ta)/1000, 'seconds')
			if(cb) cb(THIS.comparisons)
		})
	}
}
