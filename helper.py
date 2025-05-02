import random
import math
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import colorsys
from collections import defaultdict

def lcm(a, b):
	return abs(a * b) // math.gcd(a, b)

# LCM of all variables in list
def lcm_multiple(lst):
	result = lst[0]
	for val in lst[1:]:
		result = lcm(result, val)
	return result

def update_offset(eds, slot_idx, assigned_slots, min_period, current_time):
	for dev in assigned_slots[slot_idx]:
		if dev['offset'] == 0:
			# Since we have offset 0 the max offset is device period minus 1
			dev['offset'] = int(eds[dev['device_id']].period/min_period) - 1
		else:
			dev['offset'] -= 1

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

def assign_to_first_available_slot(eds, assigned_slots, start_times, current_time, slot_count, min_period, GI):

	next_slot = find_next_time_slot(start_times, current_time, min_period)

	slot_list_starting_w_next_slot = [(next_slot+i)%slot_count for i in range(slot_count)]
	
	check_offset = 0
	while True:
		for slot in slot_list_starting_w_next_slot:
			periods = []
			for dev in assigned_slots[slot]:
				periods.append(dev["period"])

			# If time slot is not empty
			if periods:
				offsets, dev_ids = get_offsets_of_time_slot(slot, eds, assigned_slots[slot], start_times, periods, min_period, current_time, GI)
			# If slot is empty, assign device to slot
			else:
				return slot, check_offset

			if check_offset not in offsets:
				for offset, period in zip(offsets, periods):
					# If any of the devices has a transmission on the checked offset then break out to check next time slot
					if (check_offset - offset) % (period // min_period) == 0:
						break

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



def prep_device_schedules(periods, offsets, min_period, number_of_slots):
    """Prepare device schedules outside the main loop for efficiency."""
    schedule_lcm = lcm_multiple(periods)
    lcm_in_min_periods = round(schedule_lcm / min_period)

    max_periods_to_check = int((1_000_000 * 60 * 60 * 24 * 7) / min_period)
    number_of_periods_to_check = min(lcm_in_min_periods, max_periods_to_check)

    # Use list comprehension instead of append
    device_schedules = [
        list(range(offset, number_of_periods_to_check, round(period / min_period)))
        for offset, period in zip(offsets, periods)
    ]

    return device_schedules, number_of_periods_to_check

def calculate_time_slot_collisions(eds, slot_idx, one_slot_assignments, start_times, requested_period, time_compatible, min_period, current_time, incompatible_with_slot, GI):
    # Initial setup
    periods = []
    for device in one_slot_assignments:
        eds[device['device_id']].global_period_rescheduling = -1
        periods.append(device["period"])

    # Get offsets and device ids
    offsets, dev_ids = get_offsets_of_time_slot(slot_idx, eds, one_slot_assignments, start_times, periods, min_period, current_time, GI)
    cpy_slot_assignments = one_slot_assignments.copy()
    
    current_period = math.floor(current_time / min_period)
        
    if start_times[slot_idx] > (current_time%min_period):
        period_of_this_slots_next_tx = current_period
    else:
        period_of_this_slots_next_tx = current_period+1

    # Main collision detection loop
    while periods:  # Continue until no periods left or no more collisions found
        # Generate device schedules for current set of devices
        device_schedules, num_periods = prep_device_schedules(periods, offsets, min_period, len(periods))
        device_count = len(device_schedules)
        device_sets = [set(lst) for lst in device_schedules]

        earliest_collision = float('inf')
        colliding_pair = None

    	# Find earliest intersection/collision in device_sets
        for i in range(device_count):
            for j in range(i+1, device_count):
            	# Get all intersections between the two sets
                intersection = device_sets[i] & device_sets[j]
                if intersection:
                    earliest = min(intersection)
                    if earliest < earliest_collision:
                        earliest_collision = earliest
                        colliding_pair = (i, j)

        # If there is a collision
        if colliding_pair:
            collision_devices = [colliding_pair[0], colliding_pair[1]]
            random.shuffle(collision_devices)
                    
            # Try to find a device that can be rescheduled
            for dev in collision_devices:
                # If device transmits before the collision, it can be rescheduled
                if offsets[dev] < earliest_collision:
                    # Calculate rescheduling period
                    device_id = cpy_slot_assignments[dev]['device_id']
                    P_resch = period_of_this_slots_next_tx + earliest_collision - int(eds[device_id].period/min_period)
                    eds[device_id].global_period_rescheduling = P_resch

                    # Remove the device from our tracking lists
                    cpy_slot_assignments.pop(dev)
                    dev_ids.pop(dev)
                    periods.pop(dev)
                    offsets.pop(dev)

                    break
        else:
        	break
        
        

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
				
				return i, current_period


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