import sys

# CHANNEL OBJECT. COUNT TX, RX, IDLE TIME. DETECT COLLISIONS
# VISUALIZE SCHEDULE FOR SINGLE TIMESLOT

class Channel:
	def __init__(self):
		self.ongoing_transmissions = 0
		self.transmission_started = -1
		self.collision_detected = False
		self.accumulated_uplink_time = 0
		self.accumulated_collision_time = 0
		self.number_of_collisions = 0


	# TODO: Add throughput code
	# TODO: Add code to not include collided transmissions into throughput

	# Returns collision boolean
	def change_mode(self, current_time, event):
		if self.ongoing_transmissions == 0:
			if event == 'TX_START':
				self.ongoing_transmissions += 1
				self.transmission_started = current_time
				return False
			elif event == 'TX_END':
				print("ERROR: CHANNEL IDLE")
				sys.exit(0)
		elif self.ongoing_transmissions >= 1:
			if event == 'TX_START':
				self.ongoing_transmissions += 1
				self.collision_detected = True
				self.number_of_collisions += 1
				#print("====================> COLLISION! Handle case", self.ongoing_transmissions)
				return True
				#sys.exit(0)
			elif event == 'TX_END':
				self.ongoing_transmissions -= 1
				if self.ongoing_transmissions == 0:
					if self.collision_detected:
						self.accumulated_collision_time += (current_time - self.transmission_started)
						self.collision_detected = False
					else:
						self.accumulated_uplink_time += (current_time - self.transmission_started)
					self.transmission_started = -1
					return False
				else:
					# Collision
					return True



class Event:
	def __init__(self, time, event_type, device, time_slot=-1, collision=False):
		self.time = time
		self.event_type = event_type
		self.device = device
		self.time_slot = time_slot
		self.collision = collision

	def __lt__(self, other):  # For heapq to sort by time
		return self.time < other.time


class ED:
	def __init__(self, ID, period, join_time, drift_direction=1, drift=10):
		self.ID = ID
		self.period = period
		self.nextTX = join_time
		self.drift_direction = drift_direction
		self.drift = drift
		self.period_until_downlink = -1
		self.global_period_rescheduling = -1
		self.uplink_times = []
		self.joined = False

		self.energy_consumption = 0 			# Joules
		self.current_mode = 'STANDBY'
		self.last_mode_change = 0
		self.voltage = 3.3

	def update_next_tx_time(self):
		#self.nextTX = self.nextTX + self.period + (self.drift_direction*self.drift*int(self.period/(1000000)))
		drift_per_microsecond = self.drift / 1_000_000
		drift_adjustment = int(self.period * drift_per_microsecond * self.drift_direction)
		nextTX_without_drift = self.nextTX + self.period
		self.nextTX += self.period + drift_adjustment
		#return self.nextTX, nextTX_without_drift


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