import sys

# CHANNEL OBJECT. COUNT TX, RX, IDLE TIME. DETECT COLLISIONS
# VISUALIZE SCHEDULE FOR SINGLE TIMESLOT


class Event:
	def __init__(self, time, event_type, device):
		self.time = time
		self.event_type = event_type
		self.device = device

	def __lt__(self, other):  # For heapq to sort by time
		return self.time < other.time


class ED:
	def __init__(self, ID, period, join_time, drift=10):
		self.ID = ID
		self.period = period
		self.nextTX = join_time
		self.drift = drift
		self.period_until_downlink = -1
		self.uplink_times = []
		self.joined = False

		self.energy_consumption = 0 			# Joules
		self.current_mode = 'STANDBY'
		self.last_mode_change = 0
		self.voltage = 3.3

	def update_next_tx_time(self):
		self.nextTX = self.nextTX + self.period + (self.drift*int(self.period/(1000000)))
		return self.nextTX


	# Both used to correct drift and reschedule
	def adjust_tx_time(self, time_shift):
		self.nextTX = self.nextTX + time_shift


	def change_mode(self, clock, event):
		if self.current_mode == 'STANDBY':
			if event == 'TX_START':
				self.current_mode = 'TX'
			elif event == 'RX_START':
				self.current_mode = 'RX'
			elif event == 'SIM_END':
				pass
			else:
				print("ERROR: IN STANDBY MODE")
				sys.exit(0)
			self.update_energy_consumption(clock, 0.0016)	# Standby mode:  	1.6  mA
		elif self.current_mode == 'TX':
			if event == 'TX_END':
				self.current_mode = 'STANDBY'
			elif event == 'SIM_END':
				pass
			else:
				print("ERROR: IN TX MODE")
				sys.exit(0)
			self.update_energy_consumption(clock, 0.12)		# Transmit mode: 	120  mA
		elif self.current_mode == 'RX':
			if event == 'RX_END':
				self.current_mode = 'STANDBY'
			elif event == 'SIM_END':
				pass
			else:
				print("ERROR: IN RX MODE")
				sys.exit(0)
			self.update_energy_consumption(clock, 0.0115)	# Receive mode:  	11.5 mA


	def update_energy_consumption(self, clock, current_ampere):
		time_in_mode = (clock - self.last_mode_change)/1_000_000				# in seconds
		self.energy_consumption += current_ampere*self.voltage*time_in_mode
		self.last_mode_change = clock