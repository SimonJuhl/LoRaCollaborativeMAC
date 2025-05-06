import sys
import random
import heapq
from classes import *
from helper import *
import cProfile

#ps = [4,5,6,7,8,9,10,11,12,13,14,15,16]

drift_directions = [1,-1]
min_device_period = 20
max_device_period = 100
def create_end_devices(n, period):

	join_times = [random.randint(1, period*5) for _ in range(n)]
	ps = [random.randint(min_device_period, max_device_period) for _ in range(n)]
	#ps = [60 for _ in range(n)]
	eds = []
	for i in range(n):
		join_time = join_times[i]
		ed = ED(i, period*ps[i], join_time, period, drift_directions[i%2])
		#ed = ED(i, period*ps[i%len(ps)], join_time, drift_directions[i%2])
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
	time_slot_assignments_ext = []
	event_queue = []
	incompatible_with_slot = []

	for i in range(1, slot_count+1):
		start_time_slot_i = int((i-1)*(slot_duration+GI))
		time_slots_start_times.append(start_time_slot_i)

	for i in range(slot_count):
		time_slot_assignments.append([])
		time_slot_assignments_ext.append([])
		incompatible_with_slot.append([])
		heapq.heappush(event_queue, Event(time=time_slots_start_times[i], event_type='UPDATE_OFFSET', device=-1, time_slot=i))

	for device in eds:
		heapq.heappush(event_queue, Event(time=device.nextTX, event_type='TX_START', device=device.ID))

	return time_slots_start_times, time_slot_assignments, time_slot_assignments_ext, event_queue, incompatible_with_slot


# n = 2013 is close to max n for 5 minute min_period and periods ps = [random.randint(20, 100) for _ in range(n)]
period = 1_000_000*60*5
tx_duration = 1_000_000*1.5
rx_duration = 1_000_000*1.5
rx_delay = 1_000_000
rx_no_preamble = int(1_000_000*0.3)								# 0.3 sec (approx: 9 symbols) rx window. 6 preamble symbols needs to be received in order to lock into signal
slot_duration = tx_duration + rx_delay + rx_duration
rescheduling_bound = 1_000_000*60*60*12
sim_end = 1_000_000*60*60*24*2
#version = 'random'
version = 'optimized_v1'

''' TODO

* Add functionality to handle what happens when a device joining the network cannot fit into the schedule.
* Add functionality that can schedule incompatible device periods.

'''

#make some code that can visualize a segment (part) of the future transmissions as a timeline. the starting time (in microseconds) of all transmissions are in a list and I want the transmissions to be 4000000 microseconds. another list is also provided, it shows the starting time of all the time slots, which the transmissions are moved into when they are drift corrected. but since the transmissions are likely drifted they will not overlap perfectly. therefore you should use these slot_starting_times to mark the beginning of all time slots. so make all transmissions a red-transparent color so we can see the vertical lines of the slot starting times. since you cannot show all the hundreds of time slots a time_slot parameter with the value will indicate the first time slot you need to visualize. just show 10 time slots / transmissions. 

def main(n):
	channel = Channel()
	eds = create_end_devices(n, period)
	slot_count, GI = get_slot_count_and_GI(period, slot_duration, drift_ppm=10, rescheduling_bound=rescheduling_bound)

	#print("slot_count:", slot_count, "\tGI:", GI)
	time_slots_start_times, time_slot_assignments, time_slot_assignments_ext, event_queue, incompatible_with_slot = init_schedule(slot_count, slot_duration, GI, eds)
	simulation_clock = 0

	#heapq.heappush(event_queue, Event(time=period*47, event_type='SHOW_SCHEDULE_ONE_SLOT', device=-1, time_slot=3))
	#heapq.heappush(event_queue, Event(time=period*8, event_type='SHOW_SCHEDULE_DRIFT_PERSPECTIVE', device=-1, time_slot=2))
	#heapq.heappush(event_queue, Event(time=period*24, event_type='SHOW_SCHEDULE_DRIFT_PERSPECTIVE', device=-1, time_slot=2))

	while simulation_clock < sim_end and event_queue:
		event = heapq.heappop(event_queue)
		simulation_clock = event.time
		device_ID = event.device
		
		#if device_ID == 1799:
		#	print(event.event_type, " \t", device_slot, device_ID, simulation_clock/period)

		#if device_slot == 2:
			#print(simulation_clock/period ,time_slot_assignments[2],"\n")
			#print(event.event_type, device_slot, device_ID, simulation_clock, time_slot_assignments[device_slot], "\n")

		if event.event_type == "UPDATE_OFFSET":

			updated_offsets = update_offset(eds, event.time_slot, time_slot_assignments, time_slot_assignments_ext, period, simulation_clock)
			
			if updated_offsets:
				time_slot_assignments_ext[event.time_slot][1] = updated_offsets
			heapq.heappush(event_queue, Event(time=event.time+period, event_type='UPDATE_OFFSET', device=-1, time_slot=event.time_slot))

		elif event.event_type == 'SHOW_SCHEDULE_ONE_SLOT':

			show_one_time_slot_schedule(eds, time_slot_assignments, event.time_slot, period)

		elif event.event_type == 'SHOW_SCHEDULE_DRIFT_PERSPECTIVE':

			show_schedule_timeline(eds, time_slot_assignments, time_slots_start_times, event_queue, event.time_slot, slot_count, period)

		elif event.event_type == 'TX_START':

			# TODO: We should not log the transmission time if a collision occur. But for now we will go with this simplification
			# Log the starting time of the transmission
			current_tx_time = eds[device_ID].nextTX
			eds[device_ID].uplink_times.append(current_tx_time)
			
			# Device updates its next transmission time
			eds[device_ID].update_next_tx_time()

			eds[device_ID].change_mode(simulation_clock, 'TX_START')

			collision = False
			if eds[device_ID].joined == True:
				collision = channel.change_mode(simulation_clock, 'TX_START')

			# If the channel object returns a collision then the tx starts, then the tx will not be received.
			# This means that the network server will not check if a drift correction needs to be performed.
			if collision:
				heapq.heappush(event_queue, Event(time=int(current_tx_time+tx_duration), event_type='TX_END', device=device_ID, time_slot=-1, collision=True))
			else:
				heapq.heappush(event_queue, Event(time=int(current_tx_time+tx_duration), event_type='TX_END', device=device_ID))


		elif event.event_type == 'TX_END':

			''' 
			Device returns to standby.
			Update the nextTX attribute of the device object. Next TX depends on the period.

			If it's the first uplink (join), assign a time slot and correct timing
			If not the first uplink, check if drift correction is needed
			If drift correction is not needed, calculate time projection for drift correction
			'''

			eds[device_ID].change_mode(simulation_clock, 'TX_END')

			current_tx_start_time = eds[device_ID].uplink_times[-1]
			nextTX_without_drift = current_tx_start_time+eds[device_ID].period

			
			# UPDATE THE ACCUMULATED TIME TRANSMITTED
			
			# If join uplink
			if eds[device_ID].joined == False:
				eds[device_ID].joined = True
				
				requested_period = eds[device_ID].period

				# Find available time slot and assign device the available slot
				if version == 'next_slot':
					slot_index, periods_from_now = assign_to_first_available_slot(eds, time_slot_assignments, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, 5)
				elif version == 'optimized_v1':
					#print(device_ID, )
					slot_index, periods_from_now = optimized_assignment_v1(eds, eds[device_ID].period, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, 10, sim_end, 5)
				elif version == 'random':
					periods_from_now = 0
					slot_index = random.randint(0, slot_count-1)
				
				time_slot_assignments[slot_index].append({"device_id": device_ID, "offset": periods_from_now, "period": requested_period})

				#print(time_slot_assignments_ext)
				if not time_slot_assignments_ext[slot_index]:
					time_slot_assignments_ext[slot_index].append([device_ID])
					time_slot_assignments_ext[slot_index].append([periods_from_now])
					time_slot_assignments_ext[slot_index].append([requested_period])
					time_slot_assignments_ext[slot_index].append([]) 					# <-- compatible periods are calculated later
				else:
					time_slot_assignments_ext[slot_index][0].append(device_ID)
					time_slot_assignments_ext[slot_index][1].append(periods_from_now)
					time_slot_assignments_ext[slot_index][2].append(requested_period)

				# Time when schedule starts over next period
				schedule_start_next_period = (math.floor((simulation_clock+period)/period))*period

				time_slots_start_time = 0
				if (simulation_clock % period) < time_slots_start_times[slot_index]:
					time_slot_start_time = schedule_start_next_period - period + time_slots_start_times[slot_index]
				else:
					time_slot_start_time = schedule_start_next_period + time_slots_start_times[slot_index]

				offset = periods_from_now*period
				start_time = time_slot_start_time + offset

				global_period = int(start_time/period)

				# Calculate time shift and adjust transmission time of device using nextTX_without_drift (which is exactly one period from the transmission just received)
				time_shift = start_time - nextTX_without_drift

				eds[device_ID].adjust_tx_time(time_shift, global_period)

				calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)
				find_compatible_periods_for_slot(slot_index, time_slot_assignments_ext, time_slots_start_times, simulation_clock, period, min_device_period, max_device_period)

				#if slot_index == 0:
					#print(round(simulation_clock/period,3),"\n", [i['device_id'] for i in time_slot_assignments[slot_index]],"\n", [eds[i['device_id']].nextTX_min_period for i in time_slot_assignments[slot_index]],"\n",[eds[i['device_id']].global_period_rescheduling for i in time_slot_assignments[slot_index]])

				#if device_ID == 269 or device_ID == 18:
					#print("YO", device_ID, slot_index, eds[device_ID].nextTX/period, eds[device_ID].global_period_rescheduling)

				# Add events to queue
				heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
			
			# If data uplink
			else:
				# This should only be called when (eds[device_ID].joined == True) since join messages are collision free and not counted for in throughpt
				collision = channel.change_mode(simulation_clock, 'TX_END')
				
				# Get time slot index value which device is assigned to
				device_slot, current_period = get_device_time_slot(device_ID, time_slot_assignments, simulation_clock, period)
				
				# If the beginning of this transmission collided or if the end of this transmission collided with another tx
				if event.collision or collision:
					print("slot",device_slot, "ID", device_ID, "is colliding at time", round(simulation_clock/period,3), eds[device_ID].period_until_downlink, int(eds[device_ID].period/period))
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(eds[device_ID].uplink_times[-1]+tx_duration+rx_delay), event_type='SHORT_RX_START', device=device_ID))

					# If the collision hindered the rescheduling of a device, then recalculate the rescheduling times
					if eds[device_ID].global_period_rescheduling == current_period:
						calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)

				elif eds[device_ID].global_period_rescheduling == current_period:
					# Remove from time_slot_assignments

					eds[device_ID].period_until_downlink = -1

					for index, device in enumerate(time_slot_assignments[device_slot]):
						if device['device_id'] == device_ID:
							#print(time_slot_assignments[device_slot][index])
							time_slot_assignments[device_slot].pop(index)

					for index, dev_id in enumerate(time_slot_assignments_ext[device_slot][0]):
						if dev_id == device_ID:
							time_slot_assignments_ext[device_slot][0].pop(index)
							time_slot_assignments_ext[device_slot][1].pop(index)
							time_slot_assignments_ext[device_slot][2].pop(index)

					if version == 'next_slot':
						slot_index, periods_from_now = assign_to_first_available_slot(eds, time_slot_assignments, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, int(eds[device_ID].period/period))
					elif version == 'optimized_v1':
						slot_index, periods_from_now = optimized_assignment_v1(eds, eds[device_ID].period, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, 10, sim_end, int(eds[device_ID].period/period))
					elif version == 'random':
						slot_index = random.randint(0, slot_count-1)
						periods_from_now = 0

					time_slot_assignments[slot_index].append({"device_id": device_ID, "offset": periods_from_now, "period": eds[device_ID].period})

					if not time_slot_assignments_ext[slot_index]:
						time_slot_assignments_ext[slot_index].append([device_ID])
						time_slot_assignments_ext[slot_index].append([periods_from_now])
						time_slot_assignments_ext[slot_index].append([eds[device_ID].period])
						time_slot_assignments_ext[slot_index].append([])						# <-- compatible periods are calculated later
					else:
						time_slot_assignments_ext[slot_index][0].append(device_ID)
						time_slot_assignments_ext[slot_index][1].append(periods_from_now)
						time_slot_assignments_ext[slot_index][2].append(eds[device_ID].period)

					# Time when schedule starts over next period
					schedule_start_next_period = (math.floor((simulation_clock+period)/period))*period

					time_slots_start_time = 0
					if (simulation_clock % period) < time_slots_start_times[slot_index]:
						time_slot_start_time = schedule_start_next_period - period + time_slots_start_times[slot_index]
					else:
						time_slot_start_time = schedule_start_next_period + time_slots_start_times[slot_index]

					offset = periods_from_now*period
					start_time = time_slot_start_time + offset

					# Calculate time shift and adjust transmission time of device using nextTX_without_drift (which is exactly one period from the transmission just received)
					time_shift = start_time - nextTX_without_drift

					global_period = int(start_time/period)

					eds[device_ID].update_rescheduling_shifts(time_shift)
					eds[device_ID].adjust_tx_time(time_shift, global_period)

					calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)
					find_compatible_periods_for_slot(slot_index, time_slot_assignments_ext, time_slots_start_times, simulation_clock, period, min_device_period, max_device_period)

					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='RX_START', device=device_ID))
					
					eds[device_ID].uplink_times = []

					#if slot_index == 0:
					#	print(round(simulation_clock/period,3),"\n", [i['device_id'] for i in time_slot_assignments[slot_index]],"\n", [eds[i['device_id']].nextTX_min_period for i in time_slot_assignments[slot_index]],"\n",[eds[i['device_id']].global_period_rescheduling for i in time_slot_assignments[slot_index]])

				# If drift correction is necessary. Since period_until_downlink was updated to 1 last iteration then it is actually 0 now
				elif eds[device_ID].period_until_downlink <= 1:

					eds[device_ID].period_until_downlink = -1
					
					time_slot_this_period = current_period*period + time_slots_start_times[device_slot]
					time_shift = time_slot_this_period - current_tx_start_time

					eds[device_ID].adjust_tx_time(time_shift)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='RX_START', device=device_ID))

					# The uplink times up until now cannot be used to calculate period_until_down when drift is corrected
					eds[device_ID].uplink_times = []

				# If NO drift correction is necessary
				else:
					# If two or more uplinks have been received since drift correction
					if len(eds[device_ID].uplink_times) >= 2:

						#if device_ID == 389:
						#	print("389 in slot", device_slot, current_tx_time/period, eds[device_ID].nextTX/period, eds[device_ID].nextTX_min_period, "no downlink")

						# How much time has the device drifted (absolute drift) since it was exactly on the time slot
						time_slot_this_period = current_period*period + time_slots_start_times[device_slot]
						device_drift_since_correction = abs(time_slot_this_period - current_tx_start_time)

						# How much time does it take before drift becomes a problem given that the device started exactly on the time slot
						t = calc_drift_correction_bound(GI, device_drift_since_correction, eds[device_ID].drift)
						
						# By flooring the quotient we know to drift correct latest when this is 0
						eds[device_ID].period_until_downlink = math.floor(t/eds[device_ID].period)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='SHORT_RX_START', device=device_ID))

		elif event.event_type == 'RX_START':	
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			channel.change_mode(simulation_clock, 'RX_START')
			heapq.heappush(event_queue, Event(time=int(simulation_clock+rx_duration), event_type='RX_END', device=device_ID))

		elif event.event_type == 'RX_END':
			eds[device_ID].change_mode(simulation_clock, 'RX_END')
			channel.change_mode(simulation_clock, 'RX_END')

		elif event.event_type == 'SHORT_RX_START':
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			channel.change_mode(simulation_clock, 'RX_START')
			heapq.heappush(event_queue, Event(time=int(simulation_clock+rx_no_preamble), event_type='RX_END', device=device_ID))


	for ed in eds:
		ed.change_mode(sim_end,'SIM_END')
		#print(ed.energy_consumption)


	slot_utilization = []
	for slot in range(slot_count):
		slot_utilization.append(0)

	fully_utilized_slots = 0

	for i, slot in enumerate(time_slot_assignments):

		if slot:
			periods = []
			for dev in slot:
				periods.append(round(dev['period']/period))

			lcm = lcm_multiple(periods)
			utilized_slots_in_lcm = 0

			for p in periods:
				utilized_slots_in_lcm += int(lcm/p)

			util = utilized_slots_in_lcm / lcm
			slot_utilization[i] = util
			if util == 1:
				fully_utilized_slots += 1

			'''print(f"\nSlot {i} with utililzation {util}")
			for dev in slot:
				print("Dev", dev['device_id'], "Period", dev['period']/period)'''

	overall_utilization = 0
	for slot in slot_utilization:
		overall_utilization += slot/slot_count

	all_periods_summed = 0
	for ed in eds:
		all_periods_summed += ed.period/period
	avg_period = all_periods_summed/n

	#print("\nOverall utilization:", overall_utilization)
	#print("Fully utilized slots:", fully_utilized_slots)
	print(n, "number of nodes")
	number_of_min_periods_during_simulation = sim_end // period
	max_uplink_time_during_simulation = number_of_min_periods_during_simulation * slot_count * tx_duration
	print("Uplink utilization:", channel.accumulated_uplink_time/max_uplink_time_during_simulation)
	print("Number of collisions:", channel.number_of_collisions,"\n")


	number_of_rescheduling_shifts = 0
	accumulated_rescheduling_shift_in_min_periods = 0
	for ed in eds:
		for shift in ed.rescheduling_shifts:
			number_of_rescheduling_shifts += 1
			accumulated_rescheduling_shift_in_min_periods += shift/period
	#	print(ed.rescheduling_shifts_in_dev_periods)
	#	print(ed.rescheduling_shifts)

	print("Rescheduling shifts", number_of_rescheduling_shifts, "average shift is", accumulated_rescheduling_shift_in_min_periods/number_of_rescheduling_shifts)

	#for ed in eds:
		#print(ed.energy_consumption)

	plot_energy_consumption_distribution(eds)
	print("Energy plot created")
	plot_rescheduling_shift_swarm_distributions(eds, period)
	print("Rescheduling shift plot created")

	#print("Average period", avg_period)


if __name__=="__main__":
	random.seed(99)

	pr = cProfile.Profile()
	pr.enable()
	ns = [3000]
	#ns = [250,500,750,1000,1250,1500,1750,2000]
	for n in ns:
		main(n=n)
	pr.disable()
	pr.dump_stats("profile_output.prof")
