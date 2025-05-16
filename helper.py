import numpy as np
import time
import random
import math
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import colorsys
from collections import defaultdict
import seaborn as sns
import copy

def lcm(a, b):
	return abs(a * b) // math.gcd(a, b)

# LCM of all variables in list
def lcm_multiple(lst):
	result = lst[0]
	for val in lst[1:]:
		result = lcm(result, val)
	return result

''' HOW time_slot_assignments_ext WORKS
[
	[									<--- ext[0]
		[id     , ...],					<--- ext[0][0]
		[offset , ...],					<--- ext[0][1]
		[period , ...]					<--- ext[0][2]
		[compat , ...]					<--- ext[0][3]
	],
	[									<--- ext[1]
		[id_1     , id_2     , ...],  	<--- ext[1][0]
		[offset_1 , offset_2 , ...],  	<--- ext[1][1]
		[period_1 , period_2 , ...]  	<--- ext[1][2]
		[compat_1 , compat_2 , ...]		<--- ext[0][3]
	],		
			↑
	   ext[1][3][0]
	
	.
	.
	.

	[]
]

'''

def update_offset(eds, slot_idx, assigned_slots, assigned_slots_ext, min_period, current_time):
	if assigned_slots[slot_idx]:
		for dev in assigned_slots[slot_idx]:
			if dev['offset'] == 0:
				# Since we have offset 0 the max offset is device period minus 1
				dev['offset'] = int(eds[dev['device_id']].period/min_period) - 1
			else:
				dev['offset'] -= 1

		updated_offsets = []
		for idx, offset in enumerate(assigned_slots_ext[slot_idx][1]):
			# index 1 is the 
			if offset == 0:
				# Since we have offset 0 the max offset is device period minus 1
				updated_offsets.append(int(eds[assigned_slots_ext[slot_idx][0][idx]].period/min_period) - 1)
			else:
				updated_offsets.append(offset-1)

		return updated_offsets


def get_offsets_of_time_slot(slot_idx, eds, already_assigned, start_times, all_periods, min_period, current_time, GI):
	dev_ids = []
	testo = []
	for dev in already_assigned:
		dev_ids.append(dev['device_id'])
		testo.append(dev['offset'])

	return testo, dev_ids

def is_compatible(slot_idx, eds, already_assigned, start_times, new_period, min_period, current_time, GI):
	periods = []

	for device in already_assigned:
		periods.append(device["period"])

	# Make list with periods of devices that are already in slot and the period of the joining device
	all_periods = periods + [new_period]

	offsets, dev_ids = get_offsets_of_time_slot(slot_idx, eds, already_assigned, start_times, all_periods, min_period, current_time, GI)

	schedule_lcm = lcm_multiple(all_periods)
	lcm_in_min_periods = round(schedule_lcm / min_period)

	if lcm_in_min_periods > 10000:
		return -1

	availability_schedule = [True] * (2*lcm_in_min_periods)

	test = [True] * (2*lcm_in_min_periods)

	# Update the availability_schedule list. If device with specific offset and period plans to send in a time slot then mark as unavailable
	for dev_id, offset, period in zip(dev_ids, offsets, periods):
		t = offset
		while t < 2*lcm_in_min_periods:
			availability_schedule[t] = False  # Mark as occupied
			#if slot_idx == 0:
			#	test[t] = dev_id
			t += round(period/min_period)

	# Offset should not be higher than period since no compatible schedule exists in that case
	for offset in range(round(new_period/min_period)):
		# Skip if starting offset is already occupied
		if not availability_schedule[offset]:
			continue

		fits = True
		for t in range(offset, 2*lcm_in_min_periods, round(new_period/min_period)):
			if not availability_schedule[t]:
				fits = False
				break

		if fits:
			return offset  # Found a valid offset

	return -1  # No valid offset found

def find_collisions_free_slot_for_x_time(slot_idx, eds, already_assigned, start_times, new_period, time_compatible, min_period, current_time, GI):
	#for slot in time_slot_assignments:
	periods = []

	for device in already_assigned:
		periods.append(device["period"])

	# Make list with periods of devices that are already in slot and the period of the joining device
	all_periods = periods + [new_period]

	# Get offsets and device ids of devices already in the slot
	offsets, dev_ids = get_offsets_of_time_slot(slot_idx, eds, already_assigned, start_times, all_periods, min_period, current_time, GI)

	# Number of minimum periods before drift becomes are problem
	number_of_collision_free_periods = math.ceil(time_compatible / min_period)

	availability_schedule = [True] * number_of_collision_free_periods

	# Update the availability_schedule list. If device with specific offset and period plans to send in a time slot then mark as unavailable
	for offset, period in zip(offsets, periods):
		t = offset
		while t < number_of_collision_free_periods:
			availability_schedule[t] = False  # Mark as occupied
			t += round(period/min_period)

	before_availability_schedule = availability_schedule
	# Offset should not be higher than period since no compatible schedule exists in that case
	for offset in range(round(new_period/min_period)):
		# Skip if starting offset is already occupied
		if not availability_schedule[offset]:
			continue

		fits = True
		for t in range(offset, number_of_collision_free_periods, round(new_period/min_period)):
			if not availability_schedule[t]:
				fits = False
				break

		if fits:
			print('Last resort. Period', round(new_period/min_period), "Offset", offset)
			print(before_availability_schedule)
			print(availability_schedule,"\n")
			#if slot_idx == 114:
				#print(offset, dev_ids, offsets, periods, test, "\n")
			return offset  # Found a valid offset

	return -1  # No valid offset found


def find_next_time_slot(start_times, current_time, min_period):
	next_slot = -1

	# The first time t greater than the current time is the next slot. If loop does not break then the next slot is slot 0
	for i, t in enumerate(start_times):
		if t > (current_time % min_period):
			next_slot = i
			break
	else:
		next_slot = 0

	return next_slot

def assign_to_first_available_slot(device_ID, eds, current_slot, assigned_slots, assigned_slots_ext, start_times, current_time, slot_count, min_period, start_offset=0):

	# Choosing the slot after the next slot such that it is not rescheduled into a new slot immediately
	next_slot = (find_next_time_slot(start_times, current_time, min_period) + 1) % slot_count

	slot_list_starting_w_next_slot = [(next_slot+i)%slot_count for i in range(slot_count)]
	
	check_offset = start_offset
	while True:

		for slot in slot_list_starting_w_next_slot:			
			if assigned_slots_ext[slot]:
				dev_ids = assigned_slots_ext[slot][0].copy()
				offsets = assigned_slots_ext[slot][1].copy()
				periods = assigned_slots_ext[slot][2].copy()
			else:
				return slot, check_offset

			if check_offset not in offsets:
				for offset, period in zip(offsets, periods):
					# If any of the devices has a transmission on the checked offset then break out to check next time slot
					if (check_offset - offset) % (period // min_period) == 0:
						break

				# If rescheduled into same slot
				if not current_slot == None and current_slot == slot:
					# If the offsets have already been updated for the devices in the slot then the schedule that we found the check_offset
					# for is one where the offsets are -1 in relation to where this device is actually going to receive its rescheduling at
					# The device is still see the current slot as offset=0 whereas the other devices see the current slot as passed
					if current_time%min_period > start_times[slot]%min_period:
						check_offset += 1
				return slot, check_offset

		check_offset += 1


def assign_to_time_slot_optimized(device_ID, eds, assigned_slots, start_times, requested_period, time_compatible, min_period, current_time, incompatible_with_slot, GI):
	# First check if period is compatible with other periods already assigned
	for slot_idx in range(len(assigned_slots)):
		
		incompatible = False
		for incompatible_period in incompatible_with_slot[slot_idx]:
			if incompatible_period == requested_period:
				incompatible = True
				break

		if assigned_slots[slot_idx] and incompatible == False:
			offset = is_compatible(slot_idx, eds, assigned_slots[slot_idx], start_times, requested_period, min_period, current_time, GI)
			
			# If it is compatible
			if offset != -1:
				return slot_idx, offset, incompatible_with_slot

			# If it is not compatible
			incompatible_with_slot[slot_idx].append(requested_period)

	# If not compatible then assign device to empty slot
	for slot_idx in range(len(assigned_slots)):
		if not assigned_slots[slot_idx]:
			return slot_idx, 0, incompatible_with_slot


	'''for slot_idx in range(len(assigned_slots)):		
			offset = find_collisions_free_slot_for_x_time(slot_idx, eds, assigned_slots[slot_idx], start_times, requested_period, time_compatible, min_period, current_time, GI)
			
			# If it is compatible
			if offset != -1:
				#print(device_ID, slot_idx)
				return slot_idx, offset, incompatible_with_slot'''

	print("NO TIME SLOTS AVAILABLE.")
	sys.exit(0)



def prep_device_schedules(periods, offsets, min_period, number_of_slots, sim_end):
    """Prepare device schedules outside the main loop for efficiency."""
    schedule_lcm = lcm_multiple(periods)
    lcm_in_min_periods = round(schedule_lcm / min_period)

    max_periods_to_check = int(sim_end / min_period)
    number_of_periods_to_check = min(lcm_in_min_periods, max_periods_to_check)

    # Use list comprehension instead of append
    device_schedules = [
        list(range(offset, number_of_periods_to_check, round(period / min_period)))
        for offset, period in zip(offsets, periods)
    ]

    return device_schedules, number_of_periods_to_check

def calculate_time_slot_collisions(eds, slot_idx, one_slot_assignments, one_slot_assignments_ext, start_times, requested_period, time_compatible, min_period, current_time, incompatible_with_slot, GI, sim_end):
    # Initial setup
    dev_ids = one_slot_assignments_ext[0].copy()
    offsets = one_slot_assignments_ext[1].copy()
    periods = one_slot_assignments_ext[2].copy()

    
    #if 29 in dev_ids and 258 in dev_ids:
     #   edid1 = dev_ids.index(29)
      #  edid2 = dev_ids.index(258)

       # print("DAMN",offsets[edid1], offsets[edid2], current_time/min_period)
    	#print("Device 29 next transmission", eds[29].nextTX/min_period, current_time/min_period)

    for device in one_slot_assignments:
        if eds[device['device_id']].global_period_rescheduling - int(current_time/min_period) < 2:
            continue
        eds[device['device_id']].global_period_rescheduling = -1
        #periods.append(device["period"])

    cpy_slot_assignments = copy.deepcopy(one_slot_assignments)
    
    current_period = math.floor(current_time / min_period)
        
    if start_times[slot_idx] > (current_time%min_period):
        period_of_this_slots_next_tx = current_period
    else:
        period_of_this_slots_next_tx = current_period+1


    non_reschedulable_colliding_pairs = []

    # Main collision detection loop
    while periods:  # Continue until no periods left or no more collisions found
        # Generate device schedules for current set of devices
        device_schedules, num_periods = prep_device_schedules(periods, offsets, min_period, len(periods), sim_end)
        device_count = len(device_schedules)
        device_sets = [set(lst) for lst in device_schedules]

        earliest_collision = float('inf')
        colliding_pair = None

        ids = [dvi['device_id'] for dvi in cpy_slot_assignments]


        #if 29 in ids and 258 in ids:
        	#print("fuck", current_time/min_period)
        	# According to this print, there is one time before it is too late where the devices could detect their rescheduling times
        	# Why dont they use it? 
        	# PRINT:
        	# fuck 4.977424263333333

    	# Find earliest intersection/collision in device_sets
        for i in range(device_count):
            for j in range(i+1, device_count):
                #if 29 in ids and 258 in ids:
                # happens when i=8 and j=32
                #if (29 == ids[i] and 258 == ids[j]) and current_time/min_period < 5:

                	#print("jeez",ids[i],i,ids[j],j, current_time/min_period)
                
                # Get all intersections between the two sets
                intersection = device_sets[i] & device_sets[j]
                #if (29 == ids[i] and 258 == ids[j]) and current_time/min_period < 5:
                 #   print("jeez",intersection, "\n",device_sets[i],"\n",device_sets[j],"\n")
                if intersection:
                    earliest = min(intersection)
                    #if (ids[i] == 29 and ids[j] == 258) or (ids[i] == 258 and ids[j] == 29):
                    #if slot_idx == 40 and :
                        #print("earliesttt",earliest, current_time/min_period)
                    if earliest < earliest_collision:
                    	# Since some collisions cannot be avoided we need to keep track of them to avoid attempting to reschedule again
                        if (i, j) in non_reschedulable_colliding_pairs:
                            continue

                        earliest_collision = earliest
                        colliding_pair = (i, j)

        # If there is a collision
        if colliding_pair:

            collision_devices = [colliding_pair[0], colliding_pair[1]]
            #print(collision_devices, len(cpy_slot_assignments), device_count, len(periods))
            #print(slot_idx, len(cpy_slot_assignments), len(periods), len(offsets))
            their_ids = cpy_slot_assignments[collision_devices[0]]['device_id'], cpy_slot_assignments[collision_devices[1]]['device_id']

            #if (29 in their_ids and 258 in their_ids):
            #    print("their_ids",earliest_collision, current_time/min_period)

            random.shuffle(collision_devices)
                    
            # Try to find a device that can be rescheduled
            for dev in collision_devices:
                # If device transmits before the collision, it can be rescheduled
                #if (29 in their_ids and 258 in their_ids):
                #	print("Device 29 next transmission", eds[29].nextTX/min_period, current_time/min_period)
                    #print("yo", their_ids, offsets[dev], earliest_collision, collision_devices, (eds[their_ids[0]].nextTX-current_time)/min_period, (eds[their_ids[1]].nextTX-current_time)/min_period)
                if offsets[dev] < earliest_collision:
                    # Calculate rescheduling period
                    device_id = cpy_slot_assignments[dev]['device_id']
                    P_resch = period_of_this_slots_next_tx + earliest_collision - int(eds[device_id].period/min_period)
                    #if (29 in their_ids and 258 in their_ids):
                    	#print("yo",device_id, P_resch)
                    eds[device_id].global_period_rescheduling = P_resch

                    # Remove the device from our tracking lists
                    cpy_slot_assignments.pop(dev)
                    dev_ids.pop(dev)
                    periods.pop(dev)
                    offsets.pop(dev)

                    break
            else:
            	non_reschedulable_colliding_pairs.append(colliding_pair)
        else:
        	break
    #if slot_idx == 40 and eds[29] and eds[258]:
    #	print(eds[29].global_period_rescheduling, eds[258].global_period_rescheduling)
        
        

def calc_drift_correction_bound(GI, already_drifted, drift_ppm):
	drift_per_us = drift_ppm / 1_000_000
	remaining_GI = GI / 2 - already_drifted  
	t = int(remaining_GI / drift_per_us)
	return t

def get_device_time_slot(ID, time_slot_assignments, current_time, min_period):
	for i in range(len(time_slot_assignments)):
		for j in range(len(time_slot_assignments[i])):
			if time_slot_assignments[i][j]['device_id'] == ID:

				if (current_time % min_period)/min_period > 0.5 and i == 0:
					current_period = math.floor(current_time / min_period) + 1
				elif (current_time % min_period)/min_period < 0.5 and (i-1) == len(time_slot_assignments):
					current_period = math.floor(current_time / min_period) - 1
				else: 
					current_period = math.floor(current_time / min_period)
				
				#if current_time >= 0:#106096985311-(1_000_000*800):
				#	print(i,current_period)

				return i, current_period



# Check if a period is compatible with all existing slot periods
def is_period_compatible(candidate_period, existing_periods):
    for existing_period in existing_periods:
        if math.gcd(candidate_period, existing_period) == 1:
            return False  # incompatible
    return True

# This will update the time_slot_assignments_ext sublist with compatible periods for the slot
# This compatibility will not guarantee compatibility. It will just tell us whether it is compatible with the all device periods individually
def find_compatible_periods_for_slot(slot_idx, assigned_slots_ext, start_times, min_period, dev_period_lower_bound, dev_period_upper_bound):
    compatible_periods = []
    existing_periods = []

    periods = assigned_slots_ext[slot_idx][2].copy()
    existing_periods = [p // min_period for p in periods]

    for candidate_period in range(dev_period_lower_bound, dev_period_upper_bound + 1):
        if is_period_compatible(candidate_period, existing_periods):
            compatible_periods.append(candidate_period)

    #print("slot",slot_idx, "compatible periods", compatible_periods, "time", current_time/min_period)
    #assigned_slots_ext[slot_idx][3] = 
    return compatible_periods


def find_collision_time_of_new_device_in_slot(dev_id, periods, offsets, min_period, check_offset, new_period, sim_end):
    updated_periods = periods + [new_period]
    updated_offsets = offsets + [check_offset]
    device_schedules, num_periods = prep_device_schedules(updated_periods, updated_offsets, min_period, len(periods), sim_end)
    device_count = len(device_schedules)
    device_sets = [set(lst) for lst in device_schedules]

    earliest_collision = float('inf')
    colliding_pair = None

    #if 1903 == dev_id:
     #   print("SKRRRT", device_sets)

	# Find earliest intersection/collision in device_sets
    for i in range(device_count-1):
        # Get all intersections between the two sets
        intersection = device_sets[i] & device_sets[-1]
        if intersection:
            earliest = min(intersection)

            # If the collision happens before check_offset which is the assignment time, then we do not care about the collision
            if earliest < earliest_collision and earliest >= check_offset:
                earliest_collision = earliest

    #print("Alternative time slot for period ", int(new_period/min_period) ," will be available from", check_offset, "to", earliest_collision)
    return earliest_collision

# This function returns the longest available time slot in a list like this [slot_idx, offset, collision_time]
# The procedure of the function is:
#	For each offset and slot, find an available slot, check how long this period can stay before collision
#	X number of available slots are found and the one that works for the longest is returned 
def find_best_time_slot_in_window(dev_id, assigned_slots_ext, start_times, current_time, min_period, slot_count, consider_x_slots, sim_end, new_period, start_offset=0):
	next_slot = (find_next_time_slot(start_times, current_time, min_period) + 1) % slot_count
	slot_list_starting_w_next_slot = [(next_slot+i)%slot_count for i in range(slot_count)]
	candidate_slots = []
	
	check_offset = start_offset
	
	while True:

		for slot in slot_list_starting_w_next_slot:			
			dev_ids = assigned_slots_ext[slot][0].copy()
			offsets = assigned_slots_ext[slot][1].copy()
			periods = assigned_slots_ext[slot][2].copy()

			if check_offset not in offsets:
				for offset, period in zip(offsets, periods):
					# If any of the devices has a transmission on the checked offset then break out to check next time slot
					if (check_offset - offset) % (period // min_period) == 0:
						break

				#print("Calculating collision for offset", check_offset, "meaning that this is not in", offsets)
				collision_time = find_collision_time_of_new_device_in_slot(dev_id, periods, offsets, min_period, check_offset, new_period, sim_end)
				candidate_slots.append([slot, check_offset, collision_time])


				#if 1893 == dev_id and 1057 in dev_ids:

				#debug1 = 489
				#debug2 = 2717
				debug1 = 1750
				debug2 = 314
				#if debug1 == dev_id and debug2 in dev_ids:
					#skrt = dev_ids.index(debug2)
					#print("find_best_time_slot_in_window", "\nOffset of dev", debug2, ":" ,offsets[skrt], ". Dev", debug1, "gets offset:", check_offset, f". Dev {debug1} and {debug2} collide in:", collision_time, ". Current time", current_time/min_period)
				#if 380 == dev_id:
				#	print("\tash", slot, slot_list_starting_w_next_slot)
					
				#if 642 == dev_id and 1608 in dev_ids:
				#	skrt = dev_ids.index(1433)
				#	print("MFER 642",dev_ids, "\n",offsets, check_offset, collision_time)
				

				if len(candidate_slots) == consider_x_slots:
					longest_non_colliding_slot = -1
					longest_non_colliding_time = -1
					for idx, c_s in enumerate(candidate_slots):
						if c_s[2] == float('inf'):
							continue
						non_colliding_time = c_s[2] - c_s[1]
						
						if non_colliding_time > longest_non_colliding_time:
							longest_non_colliding_slot = idx
							longest_non_colliding_time = non_colliding_time

					#if 489 == dev_id:
					#if 1750 == dev_id:
					#if dev_id == 1059 or dev_id == 1484:
					#	print("YO", dev_id, "is returning this [slot, check_offset, collision_time]", candidate_slots[longest_non_colliding_slot], "current time is ", current_time/min_period)
					return candidate_slots[longest_non_colliding_slot]

		check_offset += 1

def optimized_assignment_v1(eds, device_ID, assigned_slots_ext, start_times, current_slot, current_time, slot_count, min_period, consider_x_slots, sim_end, start_offset=0):

	new_period = eds[device_ID].period

	new_period_in_min = int(new_period/min_period)

	compatible_slots = []

	# Check if the period is compatible with any of the slot
	for idx, slot in enumerate(assigned_slots_ext):
		if not slot:
			continue
		if new_period_in_min in slot[3]:
			compatible_slots.append(idx)

	#if device_ID == 1059:
		#print("V1", device_ID)

	if compatible_slots:
		for slot in compatible_slots:

			dev_ids = assigned_slots_ext[slot][0].copy()
			offsets = assigned_slots_ext[slot][1].copy()
			periods = assigned_slots_ext[slot][2].copy()
			periods_in_min = [p // min_period for p in periods]

			check_offset = start_offset
			while True:
				for P_i, O_i in zip(periods_in_min, offsets):
					# If there is a collision between new device and one of existing devices
					if (check_offset - O_i) % math.gcd(new_period_in_min, P_i) == 0:
						break
				
				# If loop does not break then no collision is detected
				else:
					#print("Earliest compatibility found slot", slot, " offset", check_offset)
					#if 32 == device_ID or 255 == device_ID:
						#print("compatible", check_offset, device_ID)

					#if device_ID == 1059:
						#skrt = dev_ids.index(1484)
						#print("Compatible", device_ID, current_time/min_period, offsets[skrt], check_offset)

					if slot == current_slot and (current_time % min_period) > start_times[slot]:
						return slot, (check_offset+1)

					return slot, check_offset

				# It is not guaranteed that a slot in compatible_slots is compatible. Thus try another slot after x offsets
				if (check_offset - start_offset) > 500:
					break

				check_offset += 1

	#if device_ID == 1059:
	#	print("Not compatible", device_ID)

	# If none of the slots are compatible, check if there is an empty slot
	# If not compatible then assign device to empty slot
	for slot_idx in range(len(assigned_slots_ext)):
		if not assigned_slots_ext[slot_idx]:
			# start_offset is globel so by subtracting the current period we get the first allowed offset 
			allowed_offset = start_offset-int(current_time/min_period)
			#if 32 == device_ID or 255 == device_ID:
			#	print("empty", allowed_offset, device_ID)
			return slot_idx, allowed_offset

	best_slot = find_best_time_slot_in_window(device_ID, assigned_slots_ext, start_times, current_time, min_period, slot_count, consider_x_slots, sim_end, new_period, start_offset)
	
	#if device_ID == 1059:
	#	print("Best slot", device_ID)
	
	# If the device is rescheduled into the same slot then the offsets have already been updated for the devices in the 
	
	if best_slot[0] == current_slot: #(current_time % min_period) > start_times[slot]
		return best_slot[0], (best_slot[1] + 1)


	return best_slot[0], best_slot[1]





def update_plan_only_compatible_slots(eds, device_ID, plan, temp_ext, devices_to_pop, devices_in_window, slot_idx, start_times, min_period, dev_period_lower_bound, dev_period_upper_bound, current_time, window_periods):
	# For each device in the window
	for idx in range(len(devices_in_window[0])):

		dev_id = devices_in_window[0][idx]
		dev_offset = devices_in_window[1][idx]			# This is the number of periods from now before the next tx
		dev_period = devices_in_window[2][idx]
		dev_slot = devices_in_window[3][idx]

		dev_period_in_min = int(dev_period/min_period)

		compatible_slots = []

		# Check if the device period is compatible with any of the slots
		for comp_idx, slot in enumerate(temp_ext):
			if not slot:
				continue
			if dev_period_in_min in slot[3]:
				compatible_slots.append(comp_idx)


		found_slot = False

		# If there is at least one of the slots that are compatible
		if compatible_slots:
			# For each slot, check if 
			for slot in compatible_slots:

				dev_ids = temp_ext[slot][0]
				offsets = temp_ext[slot][1]
				periods = temp_ext[slot][2]
				periods_in_min = [p // min_period for p in periods]

				# Check only offsets that are at least one device period after the device's next transmission
				from_offset = dev_offset + dev_period_in_min + 1 		# +1 to since dev_offset does not take into account that there might go up to 1 extra minimum period before rescheduling actaully happens from when it was planned
				check_offset = from_offset
				while True:
					for P_i, O_i in zip(periods_in_min, offsets):
						# If there is a collision between new device and one of existing devices
						if (check_offset - O_i) % math.gcd(dev_period_in_min, P_i) == 0:
							break
					
					# If loop does not break then no collision is detected
					else:
						#print("Earliest compatibility found slot", slot, " offset", check_offset)
						found_slot = True

						time_until_next_slot = (int(current_time/min_period)*min_period + start_times[slot]) - current_time
						if time_until_next_slot < 0:
							time_until_next_slot += min_period

						nexttx = eds[dev_id].nextTX
						
						# If the next transmission lies outside of the window then it is bc this is the device which triggered the rescheduling
						# And it will be rescheduled immediately meaning that it has a nexttx=current_time
						if nexttx > current_time+(window_periods*min_period):
							nexttx = current_time
						time_until_next_tx = nexttx - current_time
						
						update_offset_to_correct_period = 0
						
						# Check if device will transmit before next slot. If not, subtract 1 from the offset best_slot[1]
						if time_until_next_tx > time_until_next_slot:
							passing_slot_x_times = int((time_until_next_tx-time_until_next_slot)/min_period) + 1
							#print("\t\tPassed")
							update_offset_to_correct_period = passing_slot_x_times

							if slot == dev_slot:
								if nexttx % min_period > start_times[slot]:
									update_offset_to_correct_period -= 1
								else:
									pass

						elif device_ID == dev_id and slot == dev_slot and (nexttx % min_period) > start_times[slot]:
							update_offset_to_correct_period -= 1


						# Add to plan which we use in simulator event loop
						plan[0].append(dev_id) 
						plan[1].append(slot) 
						plan[2].append(check_offset-update_offset_to_correct_period) 	# Since check offset is relative to now we need to subtract the time until the device transmits next time
						
						#if 686 == dev_id and 1576 in dev_ids:
							#skrt = dev_ids.index(1576)

							#print("686 candidate_slot", update_offset_to_correct_period, [slot, check_offset], "offset", offsets[skrt], "next tx",(eds[1413].nextTX-current_time)/min_period, "current_time", current_time/min_period)

						# We have to update temp_ext such that we do not have a collision with the new device
						temp_ext[slot][0].append(dev_id)
						temp_ext[slot][1].append(check_offset)		# New offset found
						temp_ext[slot][2].append(dev_period)


						#if 25 == dev_id:
						#	print(check_offset, dev_offset, dev_ids[12], periods_in_min[12], offsets[12], start_times[slot]/min_period)
						# Recalculate compatibility
						temp_ext[slot][3] = find_compatible_periods_for_slot(slot_idx, temp_ext, start_times, min_period, dev_period_lower_bound, dev_period_upper_bound)
						# TODO!!!!!!!!!!!!!!!!!!!
						# THIS temp[slot] slot-value is incorrect I think. Like the ones below aswell

						devices_to_pop.append(dev_id)

						break

					# It is not guaranteed that a slot in compatible_slots is compatible. Thus try another slot after x offsets
					if (check_offset - from_offset) > dev_period_in_min:
						break

					check_offset += 1

				if found_slot:
					break

	return plan, temp_ext, devices_to_pop



def adjust_offset(T_plan, T_actual, slot_idx, original_offset, min_period, start_times):
    # 1. Absolute time of planned assignment
    planned_absolute_time = (T_plan // min_period) * min_period + original_offset * min_period + start_times[slot_idx]

    # 2. Time difference between actual time and planned assignment
    delta = planned_absolute_time - T_actual

    # 3. Compute new offset from current time (floor ensures we don’t round up prematurely)
    adjusted_offset = max(0, delta // min_period)

    return adjusted_offset



# Finds device id, offset and period for all devices in window
# Makes temporary ext list without these devices 

# Either we specify some number of periods or slots for the window. If specifying slots then the window is less than one period
def optimized_assignment_v2(eds, current_device, assigned_slots_ext, start_times, window_periods, window_slots, current_time, min_period, slot_count, consider_x_slots, dev_period_lower_bound, dev_period_upper_bound, sim_end):

	# SUDDENLY IT IS NOT ENOUGH TO HAVE THE CURRENT RESCHEDULING SYSTEM. SINCE THIS NEW PROCEDURE CALCULATES THE NEW SLOTS AND OFFSETS OF ALL DEVICES IN THIS FUNCTION WE NEED TO RETURN A LIST WITH INFORMATION ABOUT WHERE THE PLANNED RESCHEDULING WILL MAKE CHANGES AND HOW THOSE CHANGES LOOK [[id...],[slot...],[offset...]].
	# THIS MEANS THAT WE NEED TO CHECK IF EVENT.DEVICE_ID IS IN THE RESCHEDULING PLANS. THEN POP THE DEVICE FROM THE PLANS.


	# SHOULD WE ONLY UPDATE THE SCHEDULE IF IT IS BETTER? IF WE DONT CARE THEN WE WILL ALWAYS GET A SCHEDULE THAT IS AS OR MORE COMPATIBLE THAN THE CURRENT.
	# BUT THE OPTIMIZED IS GOING TO COMPROMISE ON THE AMOUNT OF SHIFT. BECAUSE WE WILL RESCHEDULE DEVICES ONLY BASED ON COMPATIBILITY AND NOT CONSIDER SHIFT.
	

	# FIND DEVICES IN WINDOW
	next_slot = (find_next_time_slot(start_times, current_time, min_period) + 1) % slot_count
	slot_list_starting_w_next_slot = [(next_slot+i)%slot_count for i in range(slot_count)]

	# If we have a window of less than a period, we still need to run the outer loop once
	if window_periods == 0:
		window_periods += 1

	# If we 
	if not window_slots == 0:
		slot_list_starting_w_next_slot = slot_list_starting_w_next_slot[:window_slots]

	# List will later only contain devices outside of window
	temp_ext = copy.deepcopy(assigned_slots_ext)

	# List over all devices in window [[id...],[offset...],[period...]]
	devices_in_window = [[current_device[0]],[0],[current_device[1]], [current_device[2]]]

	# For each period that we have specified the window to be
	for p in range(window_periods):
		# For each slot in the list that starts with next slot
		for s in slot_list_starting_w_next_slot:
			indices_to_remove = []
			# For each device offset in slot number s
			for i, offset in enumerate(temp_ext[s][1]):
				# If the offset of the device is equal to the window period that we are currently checking 
				# then we want to add the device to our devices_in_window list and save its index in the 
				# assigned_slots_ext list such that we can pop it later
				if offset == p:
					# If a device has more than +1 reschedulings compared to the average, don't reschedule the device
					#if len(eds[temp_ext[s][0][i]].rescheduling_shifts) > (int(avg_resch) + 1):
					#	continue
					devices_in_window[0].append(temp_ext[s][0][i])
					devices_in_window[1].append(temp_ext[s][1][i])
					devices_in_window[2].append(temp_ext[s][2][i])
					devices_in_window[3].append(s)
					indices_to_remove.append(i)

			# Remove in reverse order to avoid index shifting issues
			for i in reversed(indices_to_remove):
				temp_ext[s][0].pop(i)
				temp_ext[s][1].pop(i)
				temp_ext[s][2].pop(i)

	#print(devices_in_window, current_time/min_period)

	# Recalculate compatibilities for temp_ext[]
	for slot_idx in range(len(temp_ext)):
		temp_ext[slot_idx][3] = find_compatible_periods_for_slot(slot_idx, temp_ext, start_times, min_period, dev_period_lower_bound, dev_period_upper_bound)
	

	# ids, slot to change to, "periods from now" relative to the time of the rescheduling
	plan = [[],[],[]]

	# Saved indexes of devices_in_window which have been added to a compatible slot, and thus need to be popped from devices_in_window
	devices_to_pop = []

	plan, temp_ext, devices_to_pop = update_plan_only_compatible_slots(eds, current_device[0], plan, temp_ext, devices_to_pop, devices_in_window, slot_idx, start_times, min_period, dev_period_lower_bound, dev_period_upper_bound, current_time, window_periods)

	debug_id1 = 2717
	debug_id2 = 489
	#if debug_id1 in devices_in_window[0]:
	#	print("This round", debug_id1, current_time/min_period)
	#if debug_id2 in devices_in_window[0]:
	#	print("This round", debug_id2, current_time/min_period)
	
	# Remove all devices that already have been assigned to a slot from devices_in_window
	for dev_id_to_pop in devices_to_pop:
		for idx, dev_id in enumerate(devices_in_window[0]):
			if dev_id_to_pop == dev_id:
				devices_in_window[0].pop(idx)
				devices_in_window[1].pop(idx)
				devices_in_window[2].pop(idx)
				devices_in_window[3].pop(idx)
				break


	#if debug_id1 in devices_in_window[0]:
	#	print("Tryiing to find the best", debug_id1, current_time/min_period)
	#if debug_id2 in devices_in_window[0]:
	#	print("Tryiing to find the best", debug_id2, current_time/min_period)

	# For each 
	for idx in range(len(devices_in_window[0])):

		dev_id = devices_in_window[0][idx]
		dev_offset = devices_in_window[1][idx]			# This is the number of periods from now before the next tx
		dev_period = devices_in_window[2][idx]
		dev_slot = devices_in_window[3][idx]

		dev_period_in_min = int(dev_period/min_period)

		# best slot = [slot_idx, offset, collision_time]
		from_offset = dev_offset + dev_period_in_min + 1
		check_offset = from_offset
		best_slot = find_best_time_slot_in_window(dev_id, temp_ext, start_times, current_time, min_period, slot_count, consider_x_slots, sim_end, dev_period, check_offset)

		# Check if the time slot best_slot[0] will be passed before the rescheduling happens.
		# Find time until next time slot.
		time_until_next_slot = (int(current_time/min_period)*min_period + start_times[best_slot[0]]) - current_time
		if time_until_next_slot < 0:
			time_until_next_slot += min_period

		nexttx = eds[dev_id].nextTX
		
		# If the next transmission lies outside of the window then it is bc this is the device which triggered the rescheduling
		# And it will be rescheduled immediately meaning that it has a nexttx=current_time
		if nexttx > current_time+(window_periods*min_period):
			nexttx = current_time
		time_until_next_tx = nexttx - current_time
		
		update_offset_to_correct_period = 0
		
		# Check if device will transmit before next slot. If not, subtract 1 from the offset best_slot[1]
		if time_until_next_tx > time_until_next_slot:
			passing_slot_x_times = int((time_until_next_tx-time_until_next_slot)/min_period) + 1
			#print("\t\tPassed")
			update_offset_to_correct_period = passing_slot_x_times

			if best_slot[0] == dev_slot:
				# If the nexttx is shifted to the right then the above calculation of passing_slot_x_times will be +1 too high
				if nexttx % min_period > start_times[best_slot[0]]:
					update_offset_to_correct_period -= 1
				else:
					pass
				#print("\t\tSame slot",update_offset_to_correct_period)
		# If it is rescheduled into the same slot but the current time is after the start_times then the offsets of the already
		# assigned devices is going to be updated already resulting in the offset that is just found being one too early
		

		elif dev_id == current_device[0] and best_slot[0] == dev_slot and (nexttx % min_period) > start_times[dev_slot]:
			# Therefore this is -1 so that it will end up adding to the offset
			update_offset_to_correct_period = -1

		#if 686 == dev_id or 1576 == dev_id or 1471 == dev_id or 2 == dev_id:
		#	print("If the planned offset correct? Dev id:",dev_id, ". update_offset_to_correct_period", update_offset_to_correct_period, ". Current time",current_time/min_period, ". Next tx", nexttx/min_period, ". start_times", start_times[best_slot[0]]/min_period)


		adj_offset = adjust_offset(current_time, nexttx, best_slot[0], dev_slot, min_period, start_times)
		#print(best_slot[1]-dev_offset-update_offset_to_correct_period, adj_offset)

		#if 1608 == dev_id:
		#	print("GODDAMN", best_slot[1]-dev_offset-update_offset_to_correct_period, best_slot[1], dev_offset, update_offset_to_correct_period)

		# Add to plan which we use in simulator event loop
		plan[0].append(dev_id) 
		plan[1].append(best_slot[0]) 												# Slot index
		plan[2].append(best_slot[1]-update_offset_to_correct_period) 	# Since check offset is relative to now we need to subtract the time until the device transmits next time
		
		# We have to update temp_ext such that we do not have a collision with the new device
		temp_ext[best_slot[0]][0].append(dev_id)
		temp_ext[best_slot[0]][1].append(best_slot[1])		# New offset found
		temp_ext[best_slot[0]][2].append(dev_period)


	return plan


	# ANOTHER VERSION OF THIS COULD BE TO ONLY REMOVE THE DEVICES WITH global_period_rescheduling-ATTRIBUTE WHICH IS NOT -1
	# THIS WOULD ALLOW US TO NOT RESCHEDULE COMPATIBLE DEVICES

	# FIRST GO THROUGH RESCH_DEVS AND CHECK IF THERE EXISTS A COMPATIBLE SLOT WITH START_TIME=DEV.PERIOD+DEV.OFFSET. IF THERE DOES UPDATE PLAN LIST WHICH IS RETURNED FROM FUNCTION AND POP DEVICE FROM RESCH_DEVS
	# FOR THE REMAINING DEVICES IN RESCH_DEVS RUN find_best_time_slot_in_window ON THEM.



	# WE SHOULD RECALCULATE RESCHEDULING OF ALL SLOTS IN THE PLAN

	# TRY TO COMPARE THE V1 AND V2 OVER LONGER PERIODS OF TIME AND TRACK THE NUMBER OF RESCHEDULING HOUR FOR TO SEE IF IT BECOMES LESS 

	# VARIATIONS:
		# NOT RESCHEDULE EVERYTHING WITHIN WINDOW. FILTER OUT COMPATIBLE DEVICE
		# CHANGING WINDOW SIZE


	''' IDEA: FIND DIFFERENCE BETWEEN global_period_rescheduling-TIME AND CURRENT TIME. HAVE SOME THRESHOLD WHICH
	DEFINES WHEN THE DIFFERENCE IS LOW ENOUGH TO BE CONSIDERED FOR RESCHEDULING EARLY ON. 
	'''


############# VISUALIZATION CODE #############

def show_one_time_slot_schedule(eds, time_slot_assignments, time_slot, min_period):
	ed_ids = []
	offsets = []
	periods = []
	for dev in time_slot_assignments[time_slot]:
		for ed in eds:
			if ed.ID == dev['device_id']:
				ed_ids.append(ed.ID)
				offsets.append(math.floor(ed.nextTX/min_period))
				periods.append(int(ed.period/min_period))
	
	schedule_lcm = lcm_multiple(periods)
	availability_schedule = [True] * (2*schedule_lcm)

	for ed_id, offset, period in zip(ed_ids, offsets, periods):
		t = offset
		while t < 2*schedule_lcm:
			availability_schedule[t] = f"{ed_id},p={period}"  # Mark as occupied
			t += round(period)

	#print("Sample schedule entries:", availability_schedule[:20])
	visualize_schedule_grid(availability_schedule)




def show_schedule_timeline(eds, time_slot_assignments, slot_starting_times, event_queue, time_slot, number_of_slots, min_period):
	event_queue.sort(key=lambda x: x.time)
	sorted_queue = sorted(event_queue, key=lambda x: x.time)

	device_ID_in_first_slot = event_queue[0].device
	beginning_slot = get_device_time_slot(device_ID_in_first_slot, time_slot_assignments)
	highest_slot = -1

	slot_list = []
	tx_start_list = []
	downlink_countdown = []

	for event in event_queue:
		if event.event_type == 'TX_START':
			
			device_ID = event.device
			slot = get_device_time_slot(device_ID, time_slot_assignments)
			min_periods_until_dl = int((eds[device_ID].period_until_downlink*eds[device_ID].period)/min_period)
			
			# If two uplinks have not been received since last drift correction:
			if min_periods_until_dl < 0:
				min_periods_until_dl = False

			if slot > highest_slot:
				highest_slot = slot
				slot_list.append(slot)
				tx_start_list.append(event.time)
				downlink_countdown.append(min_periods_until_dl)
			else:
				if beginning_slot > slot:
					slot_list.append(slot)
					tx_start_list.append(event.time)
					downlink_countdown.append(min_periods_until_dl)
				else:
					break
	

	visualize_transmissions(
		tx_start_list=tx_start_list,
		slot_list=slot_list,
		slot_starting_times=slot_starting_times,
		time_slot=time_slot,
		min_period=min_period,
		downlink_countdown=downlink_countdown
	)


################################ PLOT ######################################


def visualize_transmissions(
    tx_start_list,
    slot_list,
    slot_starting_times,
    time_slot,
    min_period,
    downlink_countdown,
    transmission_duration=4_000_000
):
    # Find all slot indices that have transmissions
    slot_indices = [i for i, slot in enumerate(slot_list) if slot >= time_slot]

    if not slot_indices:
        print("No transmissions found for or after the given time_slot.")
        return

    # Get the first relevant slots
    selected_indices = slot_indices[:8]

    # TODO: Check if non-utilized slots are skipped bc they shouldn't be

    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 2))

    for idx in selected_indices:
        tx_time = tx_start_list[idx] % min_period  # relative to the period
        slot_number = slot_list[idx]
        slot_start = slot_starting_times[slot_number] % min_period
        slot_end = (slot_start + 4_000_000) % min_period  # or min_period if you're using that directly
        next_downlink = downlink_countdown[idx]
        #if idx != selected_indices[-1]:
        #	midpoint = ((slot_starting_times[idx+1]%min_period + slot_end) / 2)

        # Draw transmission as red transparent box
        ax.add_patch(
            plt.Rectangle(
                (tx_time, 0),  # (x, y)
                transmission_duration,  # width
                1,  # height
                color='red',
                alpha=0.4
            )
        )

        # Slot start line (black dashed)
        ax.axvline(x=slot_start, color='black', linestyle='--', label='Slot Start' if idx == selected_indices[0] else "")

        # Slot end line (blue dashed)
        ax.axvline(x=slot_end, color='blue', linestyle='--', label='Slot End' if idx == selected_indices[0] else "")

        # Midpoint line (green dotted)
        #ax.axvline(x=midpoint, color='green', linestyle=':', label='Midpoint' if idx == selected_indices[0] else "")

        # Optionally label the slot
        ax.text(slot_start, 1.05, f"Slot {slot_number}", rotation=90, va='bottom', ha='center')

    ax.set_ylim(0, 1.2)
    ax.set_xlabel("Time (μs, relative to period)")
    ax.set_yticks([])
    ax.set_title(f"Transmission Timeline (starting from slot {time_slot})")
    ax.legend(loc='upper right')
    plt.tight_layout()
    plt.show()


def get_n_color_shades(base_color, n):
    """Generate n visually distinct shades of a base RGB color."""
    h, l, s = colorsys.rgb_to_hls(*base_color)
    return [colorsys.hls_to_rgb(h, min(1, max(0.25, l + (i - n//2) * 0.12)), s) for i in range(n)]

def period_to_base_color(period):
    """Define a contrasting base color per period."""
    palette = {
        6: (0.0, 0.45, 0.7),     # blue
        9: (0.9, 0.1, 0.1),      # red
        12: (0.0, 0.6, 0.2),     # green
        15: (0.7, 0.4, 0.0),     # orange
        5: (0.4, 0.0, 0.5),      # purple
        8: (0.5, 0.3, 0.9),      # lavender
        11: (0.9, 0.6, 0.0),     # amber
    }
    return palette.get(period, (0.4, 0.4, 0.4))  # fallback gray

def visualize_schedule_grid(availability_schedule):
    # Collect device entries
    device_entries = [x for x in availability_schedule if isinstance(x, str)]
    
    # Group by period
    devices_by_period = defaultdict(list)
    for entry in device_entries:
        try:
            device_id, period_str = entry.split(",p=")
            period = int(period_str)
            devices_by_period[period].append(device_id)
        except Exception as e:
            print(f"Skipping invalid entry: {entry}")

    # Generate color map
    color_map = {}
    for period, device_ids in devices_by_period.items():
        base = period_to_base_color(period)
        shades = get_n_color_shades(base, len(set(device_ids)))
        for dev_id, color in zip(sorted(set(device_ids)), shades):
            key = f"{dev_id},p={period}"
            color_map[key] = color

    max_period = max(devices_by_period.keys(), default=10)
    columns = max_period
    total = len(availability_schedule)
    rows = math.ceil(total / columns)

    fig, ax = plt.subplots(figsize=(columns, rows * 0.6))

    for i, entry in enumerate(availability_schedule):
        row = i // columns
        col = i % columns
        if isinstance(entry, str) and entry in color_map:
            color = color_map[entry]
            rect = plt.Rectangle((col, -row), 1, 1, color=color)
            ax.add_patch(rect)
        else:
            rect = plt.Rectangle((col, -row), 1, 1, edgecolor='black', facecolor='white')
            ax.add_patch(rect)

    # Grid lines
    for r in range(rows + 1):
        ax.axhline(-r, color='black', linewidth=0.5)
    for c in range(columns + 1):
        ax.axvline(c, color='black', linewidth=0.5)

    ax.set_xlim(0, columns)
    ax.set_ylim(-rows, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect('equal')

    # Legend
    patches = []
    for label, color in color_map.items():
        patches.append(mpatches.Patch(color=color, label=label))
    if patches:
        ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left', title="Device ID & Period")
    
    plt.tight_layout()
    plt.show()

def plot_rescheduling_shift_distributions(eds, min_period):
    # Flatten the lists of shifts across all devices
    shifts_in_dev_periods = [shift for ed in eds for shift in ed.rescheduling_shifts_in_dev_periods]
    shifts_in_microseconds = [shift/min_period for ed in eds for shift in ed.rescheduling_shifts]

    # Create figure with two subplots
    fig, ax1 = plt.subplots(1, 1, figsize=(10, 8), sharex=False)

    # Top: Shifts in device periods
    ax1.hist(shifts_in_microseconds, bins='sturges', color='skyblue', edgecolor='black')
    ax1.set_title('Rescheduling Shifts (in Device Periods)')
    ax1.set_xlabel('Shift (Device Periods)')
    ax1.set_ylabel('Frequency')
    ax1.grid(True)

    plt.tight_layout()
    plt.show()

def plot_rescheduling_shift_swarm_distributions(eds, period, ax):
	shifts_in_microseconds = [shift / period for ed in eds for shift in ed.rescheduling_shifts]

	if ax == None:
		plt.figure(figsize=(12, 6))
		sns.stripplot(data=shifts_in_microseconds, orient="h", jitter=0.25, alpha=0.5, size=3)
		plt.title('Rescheduling Shifts (in Min Periods)')
		plt.xlabel('Shift (Min Periods)')
		plt.grid(True)
		plt.tight_layout()
		plt.xlim((0,100))
		plt.savefig("rescheduling_shifts.png", dpi=300, bbox_inches='tight')
		#plt.show()
	else:
		sns.stripplot(
			x=shifts_in_microseconds,
			orient="h",
			jitter=0.25,
			alpha=0.5,
			size=3,
			ax=ax
		)

		ax.set_title('Rescheduling Shifts (in Min Periods)')
		ax.set_xlabel('Shift (Min Periods)')
		ax.grid(True)
		ax.set_xlim((0,100))



def plot_number_of_reschedulings(eds, ax):
    # Count reschedulings for each device
    rescheduling_counts = [len(ed.rescheduling_shifts) for ed in eds]
    bins = np.arange(0, max(rescheduling_counts)+2) - 0.5  # To center bars

    if ax == None:
        plt.figure(figsize=(12, 6))

        plt.hist(rescheduling_counts, bins=bins, color='steelblue', edgecolor='black', log=True)

        plt.title("Number of Reschedulings per Device")
        plt.xlabel("Number of Reschedulings")
        plt.ylabel("Number of Devices (log scale)")
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)

        plt.xticks(np.arange(0, max(rescheduling_counts)+1))
        plt.tight_layout()
        plt.savefig("number_of_rescheduling.png", dpi=300, bbox_inches='tight')
    else:

	    # Histogram of number of reschedulings
	    ax.hist(rescheduling_counts, bins=bins, color='steelblue', edgecolor='black', log=True)
	    ax.set_title("Number of Reschedulings per Device")
	    ax.set_xlabel("Number of Reschedulings")
	    ax.set_ylabel("Number of Devices (log scale)")
	    ax.grid(True)

def plot_energy_consumption_distribution(eds, ax):
    # Extract all energy consumption values (in joules)
    energy_values = [ed.energy_consumption for ed in eds if ed.energy_consumption is not None]

    if not energy_values:
        print("No energy consumption data available.")
        return

    # Define fine-grained bins based on data range
    bin_width = (max(energy_values) - min(energy_values)) / 100  # 100 bins
    bins = np.arange(min(energy_values), max(energy_values) + bin_width, bin_width)

    if ax == None:
        plt.figure(figsize=(10, 6))
        plt.hist(energy_values, bins=bins, color='mediumseagreen', edgecolor='black')
        plt.title('Distribution of End Device Energy Consumption')
        plt.xlabel('Energy Consumption (Joules)')
        plt.ylabel('Number of Devices')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("energy_consumption.png", dpi=300, bbox_inches='tight')
    else:

        # Create histogram
        ax.hist(energy_values, bins=bins, color='mediumseagreen', edgecolor='black')
        ax.set_title("Energy Distribution")
        ax.set_xlabel("Energy (J)")
        ax.set_ylabel("Devices")
        ax.grid(True)

    '''plt.figure(figsize=(10, 6))
    plt.hist(energy_values, bins=bins, color='mediumseagreen', edgecolor='black')
    plt.title('Distribution of End Device Energy Consumption')
    plt.xlabel('Energy Consumption (Joules)')
    plt.ylabel('Number of Devices')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("energy_consumption.png", dpi=300, bbox_inches='tight')'''
    #plt.show()