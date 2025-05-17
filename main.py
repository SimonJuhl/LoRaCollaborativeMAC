import json
import sys
import random
import heapq
from classes import *
from helper import *
import cProfile

#ps = [4,5,6,7,8,9,10,11,12,13,14,15,16]

drift_directions = [1,-1]
min_device_period = 20
max_device_period = 70
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
	rescheduling_count_each_device = []
	rescheduling_shift_each_device = []


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
		rescheduling_count_each_device.append(0)
		rescheduling_shift_each_device.append(0)

	return time_slots_start_times, time_slot_assignments, time_slot_assignments_ext, event_queue, incompatible_with_slot, rescheduling_count_each_device, rescheduling_shift_each_device


# n = 2013 is close to max n for 5 minute min_period and periods ps = [random.randint(20, 100) for _ in range(n)]
period = 1_000_000*60*5
tx_duration = 1_000_000*1.5
rx_duration = 1_000_000*1.5
rx_delay = 1_000_000
rx_no_preamble = int(1_000_000*0.3)								# 0.3 sec (approx: 9 symbols) rx window. 6 preamble symbols needs to be received in order to lock into signal
slot_duration = tx_duration + rx_delay + rx_duration
rescheduling_bound = 1_000_000*60*60*12
sim_end = 1_000_000*60*60*24*3
#version = 'random'

window_slots = 0

''' TODO

* Add functionality to handle what happens when a device joining the network cannot fit into the schedule.
* Add functionality that can schedule incompatible device periods.

'''

#make some code that can visualize a segment (part) of the future transmissions as a timeline. the starting time (in microseconds) of all transmissions are in a list and I want the transmissions to be 4000000 microseconds. another list is also provided, it shows the starting time of all the time slots, which the transmissions are moved into when they are drift corrected. but since the transmissions are likely drifted they will not overlap perfectly. therefore you should use these slot_starting_times to mark the beginning of all time slots. so make all transmissions a red-transparent color so we can see the vertical lines of the slot starting times. since you cannot show all the hundreds of time slots a time_slot parameter with the value will indicate the first time slot you need to visualize. just show 10 time slots / transmissions. 

def main(n, version, axs_energy=None, axs_shift=None, axs_resched=None):
	channel = Channel()
	eds = create_end_devices(n, period)
	slot_count, GI = get_slot_count_and_GI(period, slot_duration, drift_ppm=10, rescheduling_bound=rescheduling_bound)

	#print("slot_count:", slot_count, "\tGI:", GI)
	time_slots_start_times, time_slot_assignments, time_slot_assignments_ext, event_queue, incompatible_with_slot, rescheduling_count_each_device, rescheduling_shift_each_device = init_schedule(slot_count, slot_duration, GI, eds)
	simulation_clock = 0

	# Used during version=optimized_v2
	rescheduling_plan = []
	plan_outdated_time = 0

	hourly_rescheduling = []
	hourly_rescheduling_shift = []
	hourly_collisions = []

	last_hour_total_rescheduling = 0
	last_hour_total_rescheduling_shift = 0
	last_hour_collisions = 0


	
	heapq.heappush(event_queue, Event(time=1_000_000*60*60, event_type='GET_HOURLY_DATA', device=-1, time_slot=-1))

	window_periods = 1
	slots_to_consider_in_search_of_optimal = 20
	if "optimized_v2_wndw" in version:
		window_periods = int(version.split('wndw_',1)[1])
		print("Window periods is", window_periods)
		version = "optimized_v2"

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
			
			#if event.time_slot == 27 and simulation_clock/period > 52:
				#print("Slot 27 is updated at", simulation_clock/period)
			if updated_offsets:
				time_slot_assignments_ext[event.time_slot][1] = updated_offsets
			heapq.heappush(event_queue, Event(time=event.time+period, event_type='UPDATE_OFFSET', device=-1, time_slot=event.time_slot))

		elif event.event_type == 'GET_HOURLY_DATA':

			total_rescheduling = 0
			for slot in rescheduling_count_each_device:
				total_rescheduling += slot
			hourly_rescheduling.append(total_rescheduling - last_hour_total_rescheduling)
			last_hour_total_rescheduling = total_rescheduling


			total_rescheduling_shift = 0
			for slot in rescheduling_shift_each_device:
				total_rescheduling_shift += slot
			hourly_rescheduling_shift.append(total_rescheduling_shift - last_hour_total_rescheduling_shift)
			last_hour_total_rescheduling_shift = total_rescheduling_shift


			total_collisions = channel.number_of_collisions
			hourly_collisions.append(total_collisions-last_hour_collisions)
			last_hour_collisions = total_collisions


			heapq.heappush(event_queue, Event(time=event.time+1_000_000*60*60, event_type='GET_HOURLY_DATA', device=-1, time_slot=-1))

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
				collision, col_dev = channel.change_mode(simulation_clock, 'TX_START', device_ID)

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
			
			# Reset plan if it becomes outdated
			if plan_outdated_time < simulation_clock:
				rescheduling_plan = []

			# If join uplink
			if eds[device_ID].joined == False:
				eds[device_ID].joined = True
				
				requested_period = eds[device_ID].period

				# Find available time slot and assign device the available slot
				if version == 'next_slot':
					slot_index, periods_from_now = assign_to_first_available_slot(device_ID, eds, None, time_slot_assignments, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, 5)
				elif version == 'optimized_v1' or version == 'optimized_v2':
					#print(device_ID, )
					slot_index, periods_from_now = optimized_assignment_v1(eds, device_ID, time_slot_assignments_ext, time_slots_start_times, None, simulation_clock, slot_count, period, slots_to_consider_in_search_of_optimal, sim_end, 5)
				elif version == 'random':
					periods_from_now = random.randint(5, 10)
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
				time_slot_assignments_ext[slot_index][3] = find_compatible_periods_for_slot(slot_index, time_slot_assignments_ext, time_slots_start_times, period, min_device_period, max_device_period)
				
				#if 1576 == device_ID or 686 == device_ID:
					#print(device_ID, eds[device_ID].period/period, simulation_clock/period, eds[device_ID].nextTX/period)

				# Add events to queue
				heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
			
			# If data uplink
			else:
				# This should only be called when (eds[device_ID].joined == True) since join messages are collision free and not counted for in throughpt
				collision, col_dev = channel.change_mode(simulation_clock, 'TX_END', device_ID)
				
				if not collision:
					eds[device_ID].count_successful_tx()

				# Get time slot index value which device is assigned to
				device_slot, current_period = get_device_time_slot(device_ID, time_slot_assignments, simulation_clock, period)
				
				

				# If the beginning of this transmission collided or if the end of this transmission collided with another tx
				if event.collision or collision:
					#print("slot",device_slot, "ID", device_ID, "is colliding with ID", col_dev," at time", round(simulation_clock/period,3))
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(eds[device_ID].uplink_times[-1]+tx_duration+rx_delay), event_type='SHORT_RX_START', device=device_ID))

					# If the collision hindered the rescheduling of a device, then recalculate the rescheduling times
					if eds[device_ID].global_period_rescheduling == current_period:
						calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)

				# If the device is in the rescheduling plan

				# TODO: Dont reschedule if it is same slot and offset
				elif rescheduling_plan and (device_ID in rescheduling_plan[0]):

					idx_of_dev_in_plan = rescheduling_plan[0].index(device_ID)
					slot_index = rescheduling_plan[1][idx_of_dev_in_plan]
					periods_from_now = rescheduling_plan[2][idx_of_dev_in_plan]

					#if 1852 == device_ID:
						#print("RESCHEDDD", device_ID, eds[device_ID].period/period, simulation_clock/period, eds[device_ID].nextTX/period, periods_from_now)

					eds[device_ID].period_until_downlink = float('inf')

					# We remove the device from slot number: device_slot
					# Later we assign it to slot number: slot_index
					for index, device in enumerate(time_slot_assignments[device_slot]):
						if device['device_id'] == device_ID:
							#print(time_slot_assignments[device_slot][index])
							time_slot_assignments[device_slot].pop(index)

					for index, dev_id in enumerate(time_slot_assignments_ext[device_slot][0]):
						if dev_id == device_ID:
							time_slot_assignments_ext[device_slot][0].pop(index)
							time_slot_assignments_ext[device_slot][1].pop(index)
							time_slot_assignments_ext[device_slot][2].pop(index)

					offsets_in_schedule = periods_from_now
					
					# If a device has been rescheduled into the same slot then usually it misses the offset update of all devices in the slot
					# Therefore we check whether it missed its oppotunity, and updates its offset if that is the case
					if slot_index == device_slot and (simulation_clock % period) > time_slots_start_times[slot_index]:
						offsets_in_schedule -= 1

					time_slot_assignments[slot_index].append({"device_id": device_ID, "offset": offsets_in_schedule, "period": eds[device_ID].period})


					if not time_slot_assignments_ext[slot_index]:
						time_slot_assignments_ext[slot_index].append([device_ID])
						time_slot_assignments_ext[slot_index].append([offsets_in_schedule])
						time_slot_assignments_ext[slot_index].append([eds[device_ID].period])
						time_slot_assignments_ext[slot_index].append([])						# <-- compatible periods are calculated later
					else:
						time_slot_assignments_ext[slot_index][0].append(device_ID)
						time_slot_assignments_ext[slot_index][1].append(offsets_in_schedule)
						time_slot_assignments_ext[slot_index][2].append(eds[device_ID].period)

					# Time when schedule starts over next period
					schedule_start_next_period = (math.floor((simulation_clock+period)/period))*period

					if device_slot <= slot_index:
						start_time = (current_period + periods_from_now) * period + time_slots_start_times[slot_index]
					elif device_slot > slot_index:
						start_time = (current_period + 1 + periods_from_now) * period + time_slots_start_times[slot_index]

					# Calculate time shift and adjust transmission time of device using nextTX_without_drift (which is exactly one period from the transmission just received)
					time_shift = start_time - nextTX_without_drift

					global_period = int(start_time/period)

					#print("RESCHEDDD", device_ID, eds[device_ID].period/period, simulation_clock/period, time_slots_start_times[slot_index]/period, eds[device_ID].nextTX/period, periods_from_now)

					this_dev_resch_count, this_dev_total_resch_shift = eds[device_ID].update_rescheduling_shifts(time_shift, simulation_clock)
					rescheduling_count_each_device[device_ID] = this_dev_resch_count
					rescheduling_shift_each_device[device_ID] = this_dev_total_resch_shift

					eds[device_ID].adjust_tx_time(time_shift, global_period)


					#if 2717 == device_ID or 489 == device_ID:
					#if 1750 == device_ID or 314 == device_ID:
					#	print("RESCHED WITH PLAN", device_ID, device_slot, slot_index, periods_from_now, simulation_clock/period, eds[device_ID].nextTX/period)

					calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)
					time_slot_assignments_ext[slot_index][3] = find_compatible_periods_for_slot(slot_index, time_slot_assignments_ext, time_slots_start_times, period, min_device_period, max_device_period)

					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='RX_START', device=device_ID))


				elif eds[device_ID].global_period_rescheduling == current_period:

					eds[device_ID].period_until_downlink = float('inf')

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
						slot_index, periods_from_now = assign_to_first_available_slot(device_ID, eds, device_slot, time_slot_assignments, time_slot_assignments_ext, time_slots_start_times, simulation_clock, slot_count, period, int(eds[device_ID].period/period))
					elif version == 'optimized_v1':
						slot_index, periods_from_now = optimized_assignment_v1(eds, device_ID, time_slot_assignments_ext, time_slots_start_times, device_slot, simulation_clock, slot_count, period, slots_to_consider_in_search_of_optimal, sim_end, int(eds[device_ID].period/period))
					elif version == 'optimized_v2':
						current_device = [device_ID, eds[device_ID].period, device_slot]

						rescheduling_plan = optimized_assignment_v2(eds, current_device, time_slot_assignments_ext, time_slots_start_times, window_periods, window_slots, simulation_clock, period, slot_count, slots_to_consider_in_search_of_optimal, min_device_period, max_device_period, sim_end)

						plan_outdated_time = simulation_clock + (window_periods * period) + ((window_slots+1) * (period/slot_count))	# Adding 1 to window_slots to make the plan get outdated one slot later in order to avoid edge cases 
						# Find the index of the current device in the rescheduling plan to see what the new slot and offset is
						idx_of_dev_in_plan = rescheduling_plan[0].index(device_ID)
						slot_index = rescheduling_plan[1][idx_of_dev_in_plan]
						periods_from_now = rescheduling_plan[2][idx_of_dev_in_plan]

					elif version == 'random':
						slot_index = random.randint(0, slot_count-1)
						periods_from_now = int(eds[device_ID].period/period)
					
					offsets_in_schedule = periods_from_now
					
					# If a device has been rescheduled into the same slot then usually it misses the offset update of all devices in the slot
					# Therefore we check whether it missed its oppotunity, and updates its offset if that is the case
					if slot_index == device_slot and (simulation_clock % period) > time_slots_start_times[slot_index]:
						offsets_in_schedule -= 1

					time_slot_assignments[slot_index].append({"device_id": device_ID, "offset": offsets_in_schedule, "period": eds[device_ID].period})

					if not time_slot_assignments_ext[slot_index]:
						time_slot_assignments_ext[slot_index].append([device_ID])
						time_slot_assignments_ext[slot_index].append([offsets_in_schedule])
						time_slot_assignments_ext[slot_index].append([eds[device_ID].period])
						time_slot_assignments_ext[slot_index].append([])						# <-- compatible periods are calculated later
					else:
						time_slot_assignments_ext[slot_index][0].append(device_ID)
						time_slot_assignments_ext[slot_index][1].append(offsets_in_schedule)
						time_slot_assignments_ext[slot_index][2].append(eds[device_ID].period)

					# If the old device slot is earlier than the new, then the current_period is actually +1 since a slot is offset 0 if there is less than one minimum period until
					if device_slot <= slot_index:
						start_time = (current_period + periods_from_now) * period + time_slots_start_times[slot_index]
						#if 1852 == device_ID:
						#	print("Earlier", device_ID, device_slot, slot_index, periods_from_now, simulation_clock/period)#eds[device_ID].period/period, simulation_clock/period, eds[device_ID].nextTX/period, periods_from_now)
					elif device_slot > slot_index:
						start_time = (current_period + 1 + periods_from_now) * period + time_slots_start_times[slot_index]
						#if 1852 == device_ID:
						#	print("Later  ", device_ID, device_slot, slot_index, periods_from_now, simulation_clock/period)#eds[device_ID].period/period, simulation_clock/period, eds[device_ID].nextTX/period, periods_from_now)

					# Calculate time shift and adjust transmission time of device using nextTX_without_drift (which is exactly one period from the transmission just received)
					time_shift = start_time - nextTX_without_drift

					global_period = int(start_time/period)

					this_dev_resch_count, this_dev_total_resch_shift = eds[device_ID].update_rescheduling_shifts(time_shift, simulation_clock)
					rescheduling_count_each_device[device_ID] = this_dev_resch_count
					rescheduling_shift_each_device[device_ID] = this_dev_total_resch_shift

					eds[device_ID].adjust_tx_time(time_shift, global_period)

					
					#if 1750 == device_ID or 314 == device_ID:
					#	print("RESCHED NO PLAN", device_ID, device_slot, slot_index, periods_from_now, simulation_clock/period, eds[device_ID].nextTX/period)

					calculate_time_slot_collisions(eds, slot_index, time_slot_assignments[slot_index], time_slot_assignments_ext[slot_index], time_slots_start_times, requested_period, rescheduling_bound, period, simulation_clock, incompatible_with_slot, GI, sim_end)
					time_slot_assignments_ext[slot_index][3] = find_compatible_periods_for_slot(slot_index, time_slot_assignments_ext, time_slots_start_times, period, min_device_period, max_device_period)

					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='RX_START', device=device_ID))
					

				# If drift correction is necessary
				elif eds[device_ID].period_until_downlink <= 2:
					eds[device_ID].period_until_downlink = float('inf')
					
					time_slot_this_period = current_period*period + time_slots_start_times[device_slot]
					time_shift = time_slot_this_period - current_tx_start_time

					eds[device_ID].update_drift_correction_count(simulation_clock)
					eds[device_ID].adjust_tx_time(time_shift)

					#if device_ID == 334:
					#	print("YES CORRECT LETSGO", eds[device_ID].period_until_downlink)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='RX_START', device=device_ID))


				# If NO drift correction is necessary
				else:				
					# How much time has the device drifted (absolute drift) since it was exactly on the time slot
					time_slot_this_period = current_period*period + time_slots_start_times[device_slot]
					device_drift_since_correction = abs(time_slot_this_period - current_tx_start_time)

					# How much time does it take before drift becomes a problem given that the device started exactly on the time slot
					t = calc_drift_correction_bound(GI, device_drift_since_correction, eds[device_ID].drift)
					
					# By flooring the quotient we know to drift correct latest when this is 0
					eds[device_ID].period_until_downlink = math.floor(t/eds[device_ID].period)

					#if device_ID == 334:
						#print("NO CORRECT LETSGO", eds[device_ID].period_until_downlink)

					# Add events to queue
					heapq.heappush(event_queue, Event(time=eds[device_ID].nextTX, event_type='TX_START', device=device_ID))
					heapq.heappush(event_queue, Event(time=int(current_tx_start_time+tx_duration+rx_delay), event_type='SHORT_RX_START', device=device_ID))


				#if 2717 == device_ID or 489 == device_ID:
				#if 1750 == device_ID or 314 == device_ID:
				#	print(device_ID, eds[device_ID].period/period, simulation_clock/period, eds[device_ID].nextTX/period, eds[device_ID].global_period_rescheduling)

		elif event.event_type == 'RX_START':	
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			collision, col_dev = channel.change_mode(simulation_clock, 'RX_START', device_ID)

			#if collision:
			#	print("RX_START slot",device_slot, "ID", device_ID, "is colliding with ID", col_dev," at time", round(simulation_clock/period,3))

			heapq.heappush(event_queue, Event(time=int(simulation_clock+rx_duration), event_type='RX_END', device=device_ID))

		elif event.event_type == 'RX_END':
			eds[device_ID].change_mode(simulation_clock, 'RX_END')
			collision, col_dev = channel.change_mode(simulation_clock, 'RX_END', device_ID)

			# Find out whether it is device 334 or 1889 that is passing the guard interval
			#device_slot, current_period = get_device_time_slot(device_ID, time_slot_assignments, simulation_clock, period)
			#if device_ID == 334:
			#	print("334",simulation_clock/period,simulation_clock%period, time_slots_start_times[device_slot+1]-GI/2)

			#if collision:
			#	print("RX_END slot",device_slot, "ID", device_ID, "is colliding with ID", col_dev," at time", round(simulation_clock/period,3))

		elif event.event_type == 'SHORT_RX_START':
			eds[device_ID].change_mode(simulation_clock, 'RX_START')
			collision, col_dev = channel.change_mode(simulation_clock, 'RX_START', device_ID)

			#if collision:
			#	print("SHORT_RX_START slot",device_slot, "ID", device_ID, "is colliding with ID", col_dev," at time", round(simulation_clock/period,3))

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
	#print("Fully utilized slots:", fully_utilized_slots


	accumulated_drift_correction_count = 0
	accumulated_energy_consumption = 0
	accumulated_energy_consumption_per_device_period = [0 for i in range(min_device_period, max_device_period+1)]
	accumulated_drift_correct_count_per_device_period = [0 for i in range(min_device_period, max_device_period+1)]
	successful_tx_per_device_period = [0 for i in range(min_device_period, max_device_period+1)]
	devices_per_period = [0 for i in range(min_device_period, max_device_period+1)]
	device_periods = []
	number_of_rescheduling_shifts = 0
	accumulated_rescheduling_shift_in_min_periods = 0
	accumulated_rescheduling_count_per_device_period = [0 for i in range(min_device_period, max_device_period+1)]
	accumulated_rescheduling_shift_per_device_period = [0 for i in range(min_device_period, max_device_period+1)]
	device_rescheduling_shifts = []

	
	#for ed in eds:
		#if int(ed.period/period) == 80:
		#	print(ed.ID, ed.downlink_times)
	
	for ed in eds:
		accumulated_drift_correction_count += ed.drift_correction_count
		accumulated_energy_consumption += ed.energy_consumption
		accumulated_energy_consumption_per_device_period[int(ed.period/period)-min_device_period] += ed.energy_consumption
		accumulated_drift_correct_count_per_device_period[int(ed.period/period)-min_device_period] += ed.drift_correction_count
		successful_tx_per_device_period[int(ed.period/period)-min_device_period] += ed.successful_tx_count
		devices_per_period[int(ed.period/period)-min_device_period] += 1
		device_periods.append(int(ed.period/period))
		device_rescheduling_shifts.append([])
		for shift in ed.rescheduling_shifts:
			number_of_rescheduling_shifts += 1
			accumulated_rescheduling_shift_in_min_periods += shift/period
			accumulated_rescheduling_shift_per_device_period[int(ed.period/period)-min_device_period] += shift/period
			accumulated_rescheduling_count_per_device_period[int(ed.period/period)-min_device_period] += 1
			device_rescheduling_shifts[-1].append(shift/period)

	#print(device_rescheduling_shifts)
	#print(hourly_rescheduling_shift)
	#print(hourly_rescheduling)

	#for i in range(len(accumulated_rescheduling_count_per_device_period)):
	#	print(i, accumulated_rescheduling_count_per_device_period[i], accumulated_drift_correct_count_per_device_period[i])

	print(n, "number of nodes")
	number_of_min_periods_during_simulation = sim_end // period
	#print("TX", sum(successful_tx_per_device_period), successful_tx_per_device_period)
	max_uplink_time_during_simulation = number_of_min_periods_during_simulation * slot_count * tx_duration
	uplink_utilization = channel.accumulated_uplink_time/max_uplink_time_during_simulation
	print("Uplink utilization:", uplink_utilization)
	print("Number of collisions:", channel.number_of_collisions)


	if not number_of_rescheduling_shifts == 0:
		print("Rescheduling count", number_of_rescheduling_shifts, "\nAverage number of reschedulings", number_of_rescheduling_shifts/n, "\nAverage shift is", accumulated_rescheduling_shift_in_min_periods/number_of_rescheduling_shifts)

	#print("Return", "uplink_utilization", uplink_utilization, "accumulated_drift_correction_count", accumulated_drift_correction_count, "accumulated_energy_consumption", accumulated_energy_consumption, "number_of_rescheduling_shifts", number_of_rescheduling_shifts, "accumulated_rescheduling_shift_in_min_periods", accumulated_rescheduling_shift_in_min_periods, "accumulated_rescheduling_shift_per_device_period",accumulated_rescheduling_shift_per_device_period, "accumulated_drift_correct_count_per_device_period", accumulated_drift_correct_count_per_device_period, "accumulated_energy_consumption_per_device_period", accumulated_energy_consumption_per_device_period,"\n")
	return uplink_utilization, accumulated_drift_correction_count, accumulated_energy_consumption, number_of_rescheduling_shifts, accumulated_rescheduling_shift_in_min_periods, accumulated_rescheduling_shift_per_device_period, accumulated_rescheduling_count_per_device_period, accumulated_drift_correct_count_per_device_period, accumulated_energy_consumption_per_device_period, devices_per_period, successful_tx_per_device_period, hourly_rescheduling, hourly_rescheduling_shift, hourly_collisions, device_periods, device_rescheduling_shifts
	#print("Average energy consumption", accumulated_energy_consumption/n, "joules\n")

	if axs_energy == None or axs_shift == None or axs_resched == None:
		axs_energy = None
		axs_shift = None
		axs_resched = None

	#return channel.accumulated_uplink_time/max_uplink_time_during_simulation



	#plot_energy_consumption_distribution(eds, axs_energy)
	#plot_rescheduling_shift_swarm_distributions(eds, period, axs_shift)
	#plot_number_of_reschedulings(eds, axs_resched)
	#print(hourly_rescheduling)

	#print("Average period", avg_period)


if __name__=="__main__":
	random.seed(99)

	plot_on = False

	ns = [200,400,600,800,1000,1200,1400,1600,1800,2000,2200,2400,2600,2800,3000,3200,3400,3600]
	versions = ['random']
	#versions = ['next_slot']
	#versions = ['optimized_v1']
	#versions = ['optimized_v2']

	results_path = versions[0]+".jsonl"

	#pr = cProfile.Profile()
	#pr.enable()
	with open(results_path, "w") as f:
		for i, n in enumerate(ns):
			for j, v in enumerate(versions):
				
				if plot_on:
					ix = i
					jx = j
					if len(ns) == 1:
						ix = int(j / 2)
						jx = j % 2
					elif len(versions) == 1:
						ix = int(i / 2)
						jx = i % 2
					
					main(n=n, version=v, axs_energy=None, axs_shift=None, axs_resched=None)


				else:
					(
						uplink_utilization,
						accumulated_drift_correction_count,
						accumulated_energy_consumption,
						number_of_rescheduling_shifts,
						accumulated_rescheduling_shift_in_min_periods,
						accumulated_rescheduling_shift_per_device_period,
						accumulated_rescheduling_count_per_device_period,
						accumulated_drift_correct_count_per_device_period,
						accumulated_energy_consumption_per_device_period,
						devices_per_period, successful_tx_per_device_period,
						hourly_rescheduling, hourly_rescheduling_shift, hourly_collisions,
						device_periods, device_rescheduling_shifts
					)  = main(n=n, version=v, axs_energy=None, axs_shift=None, axs_resched=None)

					result_entry = {
						"network_size": n,
						"version": v,
						"uplink_utilization": uplink_utilization,
						"drift_correction_count": accumulated_drift_correction_count,
						"energy_consumption": accumulated_energy_consumption,
						"rescheduling_shift_count": number_of_rescheduling_shifts,
						"rescheduling_shift_sum": accumulated_rescheduling_shift_in_min_periods,
						"resched_shift_per_device_period": accumulated_rescheduling_shift_per_device_period,
						"resched_count_per_device_period": accumulated_rescheduling_count_per_device_period,
						"drift_correct_per_device_period": accumulated_drift_correct_count_per_device_period,
						"energy_per_device_period": accumulated_energy_consumption_per_device_period,
						"devices_per_period": devices_per_period,
						"successful_txs_per_device_period": successful_tx_per_device_period,
						"hourly_rescheduling": hourly_rescheduling, 
						"hourly_rescheduling_shift": hourly_rescheduling_shift,
						"hourly_collisions": hourly_collisions,
						"device_periods": device_periods, 
						"all_resched_shifts_per_device": device_rescheduling_shifts
					}

					f.write(json.dumps(result_entry) + "\n")
	


	#pr.disable()
	#pr.dump_stats("profile_output.prof")

	
	#plt.show()

	'''pr = cProfile.Profile()
	pr.enable()
	ns = [2000, 3000]
	#versions = ['random', 'optimized_v1']
	versions = ['optimized_v1']
	for n in ns:
		for v in versions:
			main(n=n, version=v)
	pr.disable()
	pr.dump_stats("profile_output.prof")'''
