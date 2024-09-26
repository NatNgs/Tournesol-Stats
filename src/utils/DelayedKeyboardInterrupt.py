import signal

class DelayedKeyboardInterrupt:
	"""
	Usage:

		with DelayedKeyboardInterrupt():
			# stuff here will not be interrupted by SIGINT
			critical_code()
	"""
	def __enter__(self):
		self.signal_received = False
		self.old_handler = signal.signal(signal.SIGINT, self.handler)

	def handler(self, sig, frame):
		self.signal_received = (sig, frame)
		print('\n\nSIGINT received within DelayedKeyboardInterrupt block. Waiting for task to end...\n')

	def __exit__(self, type, value, traceback):
		signal.signal(signal.SIGINT, self.old_handler)
		if self.signal_received:
			self.old_handler(*self.signal_received)
