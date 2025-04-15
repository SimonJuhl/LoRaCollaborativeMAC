import random
import heapq
from classes import *
from helper import *

ps = [4,6,9]
def create_end_devices(n, period):
	eds = []
	for i in range(n):
		join_time = random.randint(0, period)		# nodes join within first period
		#ed = ED(i, period*(1+i%3), join_time)
		#ed = ED(i, period*3*(2-i%2), join_time)
		#ed = ED(i, period*(3+(2*(i%2))), join_time)
		ed = ED(i, period*ps[i%3], join_time)
		print(ed.period/period)
		eds.append(ed)
	return eds

def get_slot_count_and_GI(period, slot_duration, drift_ppm, rescheduling_bound):
	drift_per_us = drift_ppm / 1_000_000
	min_GI = 2 * round(rescheduling_bound * drift_per_us)
	slot_count = math.floor(period/(slot_duration+min_GI))
	GI = (period-(slot_count*slot_duration))/slot_count
	return slot_count, GI

def init_schedule(slot_count, slot_duration, GI, eds):
	time_slots_start_times = []
	time_slot_assignments = []
	event_queue = []

	for i in range(1, slot_count+1):
		start_time_slot_i = int((i-1)*(slot_duration+GI))
		time_slots_start_times.append(start_time_slot_i)

	for i in range(slot_count):
		time_slot_assignments.append([])

	for device in eds:
		heapq.heappush(event_queue, Event(time=device.nextTX, event_type='TX_START', device=device.ID))

	return time_slots_start_times, time_slot_assignments, event_queue


n = 80
period = 1_000_000*60*30
tx_duration = 1_000_000*1.5
rx_duration = 1_000_000*1.5
rx_delay = 1_000_000
rx_no_preamble = int(1_000_000*0.3)								# 0.3 sec (approx: 9 symbols) rx window. 6 preamble symbols needs to be received in order to lock into signal
slot_duration = tx_duration + rx_delay + rx_duration

eds = create_end_devices(n, period)
slot_count, GI = get_slot_count_and_GI(period, slot_duration, drift_ppm=10, rescheduling_bound=1_000_000*60*60*24)
time_slots_start_times, time_slot_assignments, event_queue = init_schedule(slot_count, slot_duration, GI, eds)
sim_end = 1_000_000*60*60*24

print(slot_count)

def main():
	simulation_clock = 0
	while simulation_clock < sim_end and event_queue:
		event = heapq.heappop(event_queue)
		simulation_clock = event.time
		device_ID = event.device

		#if device_ID == 0 and event.event_type == 'TX_END':
		#	print("yo", simulation_clock/period)

		if event.event_type == 'TX_START':
			
			eds[device_ID].change_mode(simulation_clock, 'TX_START')
			heapq.heappush(event_queue, Event(time=int(eds[device_ID].nextTX+tx_duration), event_type='TX_END', device=device_ID))

		elif event.event_type == 'TX_END':

			''' 
			Device returns to standby.
			Update the nextTX attribute of the device object. Next TX depends on the period.

			If it's the first uplink (join), assign a time slot and correct timing
			If not the first uplink, check if drift correction is needed
			If drift correction is not needed, calculate time projection for drift correction
			'''

			eds[device_ID].change_mode(simulation_clock, 'TX_END')

			# Log the time of the transmission just received
			current_tx_start_time = eds[device_ID].nextTX
			eds[device_ID].uplink_times.append(current_tx_start_time)

			# Device updates its next transmission time
			eds[device_ID].update_next_tx_time()
			
			# UPDATE THE ACCUMULATED TIME TRANSMITTED
			
			# If join uplink
			if eds[device_ID].joined == False:
				eds[device_ID].joined = True
				
				requested_period = eds[device_ID].period

				# Find available time slot and assign device the available slot
				slot_index, periods_from_now = assign_to_time_slot(eds, time_slot_assignments, requested_period, period, simulation_clock)
				time_slot_assignments[slot_index].append({"device_id": device_ID, "period": requested_period})

				# Time when schedule starts over next period
				schedule_start_next_period = (math.floor((simulation_clock+period)/period))*period
				
				# Global time of assigned slot: Next period start + time slot offset in the period + number of periods to wait
				start_time = schedule_start_next_period + time_slots_start_times[slot_index] + (periods_from_now*period)

				# Calculate time shift and adjust transmission time of device
				time_shift = start_time - eds[device_ID].nextTX
				eds[device_ID].adjust_tx_time(time_shift)

				#print(device_ID, eds[device_ID].nextTX/period)

				# Add events to queue
				heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
				heapq.heappush(event_queue, Event(time=current_tx_start_time+tx_duration+rx_delay, event_type='RX_START', device=device_ID))

			# If data uplink
			else:
				# If drift correction is necessary. Since period_until_downlink was updated to 1 last iteration then it is actually 0 now
				if eds[device_ID].period_until_downlink == 1:

					eds[device_ID].period_until_downlink = -1
					
					# Get time slot index value which device is assigned to
					device_slot = get_device_time_slot(device_ID, time_slot_assignments)

					#print(device_slot, device_ID, eds[device_ID].period/period, (eds[device_ID].nextTX-simulation_clock)/period, simulation_clock/period, "check")

					# TODO: REVISIT THIS. DON'T THINK IT'S CORRECT ANYMORE
					# Calculate offset for the device to shift its transmission into the time slot
					start_time = time_slots_start_times[device_slot]
					current_time = current_tx_start_time % period
					time_shift = start_time - current_time
					eds[device_ID].adjust_tx_time(time_shift)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=current_tx_start_time+tx_duration+rx_delay, event_type='RX_START', device=device_ID))

					# The uplink times up until now cannot be used to calculate period_until_down when drift is corrected
					eds[device_ID].uplink_times = []

				# If NO drift correction is necessary
				else:
					# If two or more uplinks have been received since drift correction
					if len(eds[device_ID].uplink_times) >= 2:

						# CALCULATE DRIFT GIVEN LAST TWO UPLINK TIMES AND THE CORRECT PERIOD TIME

						# Get time slot index value
						device_slot = get_device_time_slot(device_ID, time_slot_assignments)

						#print(device_slot, device_ID, eds[device_ID].period/period, (eds[device_ID].nextTX-simulation_clock)/period, simulation_clock/period)

						# How much time has the device drifted (absolute drift) since it was exactly on the time slot
						device_drift_since_correction = abs(time_slots_start_times[device_slot] - (current_tx_start_time % period))

						# How much time does it take before drift becomes a problem given that the device started exactly on the time slot
						t = calc_drift_correction_bound(GI, device_drift_since_correction, eds[device_ID].drift)
						
						# By flooring the quotient we know to drift correct latest when this is 0
						eds[device_ID].period_until_downlink = math.floor(t/eds[device_ID].period)

						#print(device_ID, eds[device_ID].period/period, eds[device_ID].period_until_downlink)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=current_tx_start_time+tx_duration+rx_delay, event_type='SHORT_RX_START', device=device_ID))

		elif event.event_type == 'RX_START':	
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			heapq.heappush(event_queue, Event(time=simulation_clock+rx_duration, event_type='RX_END', device=device_ID))

		elif event.event_type == 'RX_END':
			eds[device_ID].change_mode(simulation_clock, 'RX_END')

		elif event.event_type == 'SHORT_RX_START':
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			heapq.heappush(event_queue, Event(time=simulation_clock+rx_no_preamble, event_type='RX_END', device=device_ID))

		elif event.event_type == 'SHORT_RX_END':
			eds[device_ID].change_mode(simulation_clock, 'RX_END')


	for ed in eds:
		ed.change_mode(sim_end,'SIM_END')
		#print(ed.energy_consumption)

	for slot in time_slot_assignments:
		if slot:
			print("\nSlot:")
			for dev in slot:
				print("Dev", dev['device_id'], "Period", dev['period']/period)

if __name__=="__main__":
	main()
