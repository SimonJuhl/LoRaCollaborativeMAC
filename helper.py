import math

def lcm(a, b):
	return abs(a * b) // math.gcd(a, b)

# LCM of all variables in list
def lcm_multiple(lst):
	result = lst[0]
	for val in lst[1:]:
		result = lcm(result, val)
	return result

def is_compatible(eds, already_assigned, new_period, min_period, current_time):
	periods = []
	offsets = []
	for device in already_assigned:
		periods.append(device["period"])
		dev_id = device["device_id"]

		# Find number of periods until devices use the time slot again (offset)
		for ed in eds:
			if ed.ID == dev_id:
				offset = math.floor((ed.nextTX-current_time) / min_period)
				offsets.append(offset)

	all_periods = periods + [new_period]
	schedule_lcm = lcm_multiple(all_periods)
	lcm_in_min_periods = round(schedule_lcm / min_period)
	availability_schedule = [True] * (2*lcm_in_min_periods)

	for offset, period in zip(offsets, periods):
		t = offset
		while t < 2*lcm_in_min_periods:
			availability_schedule[t] = False  # Mark as occupied
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

def assign_to_time_slot(eds, assigned_slots, requested_period, min_period, current_time):
	# First check if period is compatible with other periods already assigned
	for slot_idx in range(len(assigned_slots)):
		if assigned_slots[slot_idx]:
			offset = is_compatible(eds, assigned_slots[slot_idx], requested_period, min_period, current_time)
			if offset != -1:
				return slot_idx, offset

	# If not compatible then assign device to empty slot
	for slot_idx in range(len(assigned_slots)):
		if not assigned_slots[slot_idx]:
			return slot_idx, 0

	print("NO TIME SLOTS AVAILABLE.")
	sys.exit(0)

def calc_drift_correction_bound(GI, already_drifted, drift_ppm):
	drift_per_us = drift_ppm / 1_000_000
	remaining_GI = GI / 2 - already_drifted  
	t = int(remaining_GI / drift_per_us)
	return t

def get_device_time_slot(ID, time_slot_assignments):
	for i in range(len(time_slot_assignments)):
		for j in range(len(time_slot_assignments[i])):
			if time_slot_assignments[i][j]['device_id'] == ID:
				return i