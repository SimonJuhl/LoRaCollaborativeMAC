import numpy as np
import time
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


''' HOW time_slot_assignments_ext WORKS
[
	[									<--- ext[0]
		[id     , ...],					<--- ext[0][0]
		[offset , ...],					<--- ext[0][1]
		[period , ...]					<--- ext[0][2]
	],
	[									<--- ext[1]
		[id_1     , id_2     , ...],  	<--- ext[1][0]
		[offset_1 , offset_2 , ...],  	<--- ext[1][1]
		[period_1 , period_2 , ...]  	<--- ext[1][2]
	],		
			↑
	   ext[1][2][0]
	
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

def assign_to_first_available_slot(eds, assigned_slots, assigned_slots_ext, start_times, current_time, slot_count, min_period, start_offset=0):

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

    for device in one_slot_assignments:
        eds[device['device_id']].global_period_rescheduling = -1
        #periods.append(device["period"])

    cpy_slot_assignments = one_slot_assignments.copy()
    
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

    	# Find earliest intersection/collision in device_sets
        for i in range(device_count):
            for j in range(i+1, device_count):
                # Get all intersections between the two sets
                intersection = device_sets[i] & device_sets[j]
                if intersection:
                    earliest = min(intersection)
                    if earliest < earliest_collision:
                    	# Since some collisions cannot be avoided we need to keep track of them to avoid attempting to reschedule again
                        if (i, j) in non_reschedulable_colliding_pairs:
                            continue

                        earliest_collision = earliest
                        colliding_pair = (i, j)

        # If there is a collision
        if colliding_pair:
            collision_devices = [colliding_pair[0], colliding_pair[1]]
            their_ids = cpy_slot_assignments[collision_devices[0]]['device_id'], cpy_slot_assignments[collision_devices[1]]['device_id']

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
            	non_reschedulable_colliding_pairs.append(colliding_pair)
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
def find_compatible_periods_for_slot(slot_idx, assigned_slots_ext, start_times, current_time, min_period, dev_period_lower_bound, dev_period_upper_bound):
    compatible_periods = []
    existing_periods = []

    periods = assigned_slots_ext[slot_idx][2].copy()
    existing_periods = [p // min_period for p in periods]

    for candidate_period in range(dev_period_lower_bound, dev_period_upper_bound + 1):
        if is_period_compatible(candidate_period, existing_periods):
            compatible_periods.append(candidate_period)

    print("slot",slot_idx, "compatible periods", compatible_periods, "time", current_time/min_period)
    assigned_slots_ext[slot_idx][3] = compatible_periods




def optimized_assignment_v1(eds, slot_idx, new_period, assigned_slots_ext, start_times, current_time, slot_count, min_period, start_offset=0):

	compatible_slots = []

	# Check if the period is compatible with any of the slot
	for idx, slot in enumerate(assigned_slots_ext):
		if new_period in slot[3]:
			compatible_slots.append(idx)


	if compatible_slots:
		earliest_slot = float('inf')
		earliest_offset = float('inf')
		new_period_in_min = int(new_period/min_period)
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
					if check_offset <= earliest_offset and slot < earliest_slot:
						earliest_offset = check_offset
						earliest_slot = slot
					break

				check_offset += 1

		print("Earliest compatibility found slot", earliest_slot, " offset", earliest_offset)
		return earliest_slot, earliest_offset


	# If none of the slots are compatible, check if there is an empty slot
	else:
		# If not compatible then assign device to empty slot
		for slot_idx in range(len(assigned_slots_ext)):
			if not assigned_slots_ext[slot_idx]:
				return slot_idx, 0




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

def plot_rescheduling_shift_distributions(eds):
    # Flatten the lists of shifts across all devices
    shifts_in_dev_periods = [shift for ed in eds for shift in ed.rescheduling_shifts_in_dev_periods]
    shifts_in_microseconds = [shift for ed in eds for shift in ed.rescheduling_shifts]

    # Create figure with two subplots
    fig, ax1 = plt.subplots(1, 1, figsize=(10, 8), sharex=False)

    # Top: Shifts in device periods
    ax1.hist(shifts_in_dev_periods, bins='sturges', color='skyblue', edgecolor='black')
    ax1.set_title('Rescheduling Shifts (in Device Periods)')
    ax1.set_xlabel('Shift (Device Periods)')
    ax1.set_ylabel('Frequency')
    ax1.grid(True)

    '''# Bottom: Shifts in microseconds
    ax2.hist(shifts_in_microseconds, bins='sturges', color='salmon', edgecolor='black')
    ax2.set_title('Rescheduling Shifts (in Microseconds)')
    ax2.set_xlabel('Shift (µs)')
    ax2.set_ylabel('Frequency')
    ax2.grid(True)'''

    plt.tight_layout()
    plt.show()


def plot_energy_consumption_distribution(eds):
    # Extract all energy consumption values (in joules)
    energy_values = [ed.energy_consumption for ed in eds if ed.energy_consumption is not None]

    if not energy_values:
        print("No energy consumption data available.")
        return

    # Define fine-grained bins based on data range
    bin_width = (max(energy_values) - min(energy_values)) / 100  # 100 bins
    bins = np.arange(min(energy_values), max(energy_values) + bin_width, bin_width)

    # Create histogram
    plt.figure(figsize=(10, 6))
    plt.hist(energy_values, bins=bins, color='mediumseagreen', edgecolor='black')
    plt.title('Distribution of End Device Energy Consumption')
    plt.xlabel('Energy Consumption (Joules)')
    plt.ylabel('Number of Devices')
    plt.grid(True)
    plt.tight_layout()
    plt.show()