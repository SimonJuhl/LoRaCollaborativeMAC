from itertools import product
import math
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from collections import defaultdict
import os

sns.set(style="whitegrid")

def load_jsonl(file_path, version_name=None):
    data = []
    with open(file_path, "r") as f:
        for line in f:
            entry = json.loads(line)
            entry["version"] = version_name or os.path.basename(file_path)
            data.append(entry)
    return data

def group_indexed_data(entries, value_key, device_key, group_range=(20, 70), step=10):
    grouped = defaultdict(list)
    for entry in entries:
        values = entry.get(value_key, [])
        devices = entry.get(device_key, [])
        version = entry["version"]
        net_size = entry["network_size"]

        for i in range(len(values)):
            period = 20 + i
            if period > group_range[1]:
                continue
            group_start = (period // step) * step
            group_label = f"{group_start}-{min(group_start + step - 1, group_range[1])}"
            val = values[i]
            dev_count = devices[i] if i < len(devices) else 1
            if dev_count > 0:
                grouped[(version, net_size, group_label)].append(val / dev_count)
    return grouped

def group_indexed_data_per_version(entries, value_key, device_key, group_range=(20, 70), step=10):
    grouped = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        values = entry.get(value_key, [])
        devices = entry.get(device_key, [])
        version = entry["version"]
        net_size = entry["network_size"]

        for i in range(len(values)):
            period = 20 + i
            if period > group_range[1]:
                continue
            group_start = (period // step) * step
            group_label = f"{group_start}-{min(group_start + step - 1, group_range[1])}"
            val = values[i]
            dev_count = devices[i] if i < len(devices) else 1
            if dev_count > 0:
                avg_val = val / dev_count
                grouped[version][(net_size, group_label)].append(avg_val)
    return grouped

def plot_utilization(data, nw_sz):
    df = pd.DataFrame(data)
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df, x="network_size", y="uplink_utilization", hue="version", marker="o")
    plt.title("Uplink Utilization vs Number of Devices")
    plt.xlabel("Number of Devices")
    plt.ylabel("Uplink Utilization")
    plt.legend(title="Version")
    plt.tight_layout()
    plt.show()

# Is this actually dividing with the correct value? I would think it should be the number of devices in that group.
def plot_avg_shift(data, nw_sz):
    rows = []
    for entry in data:
        if not entry["network_size"] in nw_sz:
            continue
        avg_shift = entry["rescheduling_shift_sum"] / max(1, entry["network_size"])
        rows.append({
            "version": entry["version"],
            "network_size": entry["network_size"],
            "avg_shift": avg_shift / (3*24)
        })
    df = pd.DataFrame(rows)
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df, x="network_size", y="avg_shift", hue="version", marker="o")
    plt.title("Average Rescheduling Shift vs Number of Devices")
    plt.xlabel("Number of Devices")
    plt.ylabel("Avg Rescheduling Shift (hours)")
    plt.tight_layout()
    plt.show()



def plot_avg_downlink(data, nw_sz):
    rows = []
    for entry in data:
        if not entry["network_size"] in nw_sz:
            continue
        total_drift_correct = sum(entry["drift_correct_per_device_period"])
        total_resched_count = sum(entry["resched_count_per_device_period"])
        avg_drift_correct = total_drift_correct / max(1, entry["network_size"])
        avg_resched_count = total_resched_count / max(1, entry["network_size"])

        rows.append({
            "version": entry["version"],
            "network_size": entry["network_size"],
            "avg_resched_count": (avg_resched_count + avg_drift_correct) / (3*24)
        })
    df = pd.DataFrame(rows)
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df, x="network_size", y="avg_resched_count", hue="version", marker="o")
    plt.title("Average number of downlinks each hour for different network sizes")
    plt.xlabel("Number of Devices")
    plt.ylabel("Average numbe of downlinks per hours")
    plt.tight_layout()
    plt.show()

def plot_avg_downlink_v2(data, nw_sz):
    rows = []
    for entry in data:
        if entry["network_size"] not in nw_sz:
            continue

        version = entry["version"]
        net_size = entry["network_size"]

        total_drift_correct = sum(entry.get("drift_correct_per_device_period", []))
        total_resched_count = sum(entry.get("resched_count_per_device_period", []))

        avg_drift_correct = total_drift_correct / max(1, net_size)
        avg_resched_count = total_resched_count / max(1, net_size)

        # Combined downlink usage per hour
        rows.append({
            "version": version,
            "network_size": net_size,
            "type": "Drift + Resched",
            "downlinks_per_hour": (avg_resched_count + avg_drift_correct) / (3*24)
        })

        # Drift-only downlink usage per hour
        rows.append({
            "version": version,
            "network_size": net_size,
            "type": "Drift Only",
            "downlinks_per_hour": avg_drift_correct / (3*24)
        })

    df = pd.DataFrame(rows)

    plt.figure(figsize=(10, 6))
    sns.lineplot(
        data=df,
        x="network_size",
        y="downlinks_per_hour",
        hue="version",
        style="type",
        marker="o"
    )
    plt.title("Average Number of Downlinks per Hour per Device")
    plt.xlabel("Number of Devices")
    plt.ylabel("Downlinks per Hour")
    plt.tight_layout()
    plt.show()


def plot_avg_shift_by_period_group(data, yaxis_bound=None):
    grouped_shift = defaultdict(float)
    grouped_devices = defaultdict(int)

    for entry in data:
        values = entry.get("resched_shift_per_device_period", [])
        devices = entry.get("devices_per_period", [])
        version = entry["version"]
        net_size = entry["network_size"]

        for i in range(min(len(values), len(devices))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_shift[key] += values[i]
            grouped_devices[key] += devices[i]

    # Prepare data
    versions = set(k[0] for k in grouped_shift.keys())
    n_versions = len(versions)
    cols = 2
    rows = math.ceil(n_versions / cols)

    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=False)
    axs = axs.flatten()

    for idx, version in enumerate(versions):
        rows_data = []
        for (v, net_size, group_label) in grouped_shift:
            if v != version:
                continue
            dev_count = grouped_devices[(v, net_size, group_label)]
            if dev_count > 0:
                avg_shift = grouped_shift[(v, net_size, group_label)] / dev_count
                rows_data.append({
                    "network_size": net_size,
                    "period_group": group_label,
                    "avg_shift": avg_shift / (3*24)
                })

        df = pd.DataFrame(rows_data)
        if df.empty:
            continue

        sns.lineplot(data=df, x="period_group", y="avg_shift", hue="network_size", marker="o", ax=axs[idx])
        axs[idx].set_title(f"Avg Rescheduling Shift ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Avg Shift (hours)")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")
        if not yaxis_bound == None:
            axs[idx].set_ylim((0,yaxis_bound))

    # Hide unused subplots
    for j in range(idx + 1, len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

def plot_avg_resched_count_by_period_group(data, yaxis_bound=None):
    grouped_count = defaultdict(float)
    grouped_devices = defaultdict(int)

    for entry in data:
        values = entry.get("resched_count_per_device_period", [])
        devices = entry.get("devices_per_period", [])
        version = entry["version"]
        net_size = entry["network_size"]

        for i in range(min(len(values), len(devices))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_count[key] += values[i]
            grouped_devices[key] += devices[i]

    # Prepare data
    versions = set(k[0] for k in grouped_count.keys())
    n_versions = len(versions)
    cols = 2
    rows = math.ceil(n_versions / cols)

    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=False)
    axs = axs.flatten()

    for idx, version in enumerate(versions):
        rows_data = []
        for (v, net_size, group_label) in grouped_count:
            if v != version:
                continue
            dev_count = grouped_devices[(v, net_size, group_label)]
            if dev_count > 0:
                avg_count = grouped_count[(v, net_size, group_label)] / dev_count
                rows_data.append({
                    "network_size": net_size,
                    "period_group": group_label,
                    "avg_resched_count": avg_count
                })

        df = pd.DataFrame(rows_data)
        if df.empty:
            continue

        sns.lineplot(data=df, x="period_group", y="avg_resched_count", hue="network_size", marker="o", ax=axs[idx])
        axs[idx].set_title(f"Avg Rescheduling Count ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Avg Reschedulings")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")
        if not yaxis_bound == None:
            axs[idx].set_ylim((-1,yaxis_bound))

    # Hide unused subplots
    for j in range(idx + 1, len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

def plot_avg_shift_by_period_group_bar(data, nw_sz, yaxis_bound=None):
    grouped_shift = defaultdict(float)
    grouped_devices = defaultdict(int)

    for entry in data:
        values = entry.get("resched_shift_per_device_period", [])
        devices = entry.get("devices_per_period", [])
        version = entry["version"]
        net_size = entry["network_size"]
        if not net_size in nw_sz:
            continue

        for i in range(min(len(values), len(devices))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_shift[key] += values[i]
            grouped_devices[key] += devices[i]

    desired_order = ["Random", "Next Slot", "Optimized V1", "Optimized V2"]
    versions_in_data = [v for v in desired_order if any(k[0] == v for k in grouped_shift)]
    
    cols = 2
    rows = math.ceil(len(versions_in_data) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=False)
    axs = axs.flatten()

    for idx, version in enumerate(versions_in_data):
        rows_data = []
        for (v, net_size, group_label) in grouped_shift:
            if v != version:
                continue
            dev_count = grouped_devices[(v, net_size, group_label)]
            if dev_count > 0:
                avg_shift = grouped_shift[(v, net_size, group_label)] / dev_count
                rows_data.append({
                    "network_size": net_size,
                    "period_group": group_label,
                    "avg_shift": avg_shift
                })

        df = pd.DataFrame(rows_data)
        if df.empty:
            continue

        sns.barplot(data=df, x="period_group", y="avg_shift", hue="network_size", ax=axs[idx])
        axs[idx].set_yscale("log")
        axs[idx].set_title(f"Avg Rescheduling Shift ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Avg Shift (log scale)")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")
        if yaxis_bound is not None:
            axs[idx].set_ylim((1e-1, yaxis_bound))

    for j in range(idx + 1, len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

def plot_avg_resched_count_by_period_group_bar(data, nw_sz, yaxis_bound=None):
    grouped_count = defaultdict(float)
    grouped_devices = defaultdict(int)

    for entry in data:
        values = entry.get("resched_count_per_device_period", [])
        devices = entry.get("devices_per_period", [])
        version = entry["version"]
        net_size = entry["network_size"]
        if not net_size in nw_sz:
            continue

        for i in range(min(len(values), len(devices))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_count[key] += values[i]
            grouped_devices[key] += devices[i]

    desired_order = ["Random", "Next Slot", "Optimized V1", "Optimized V2"]
    versions_in_data = [v for v in desired_order if any(k[0] == v for k in grouped_count)]
    
    cols = 2
    rows = math.ceil(len(versions_in_data) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=False)
    axs = axs.flatten()

    for idx, version in enumerate(versions_in_data):
        rows_data = []
        for (v, net_size, group_label) in grouped_count:
            if v != version:
                continue
            dev_count = grouped_devices[(v, net_size, group_label)]
            if dev_count > 0:
                avg_count = grouped_count[(v, net_size, group_label)] / dev_count
                rows_data.append({
                    "network_size": net_size,
                    "period_group": group_label,
                    "avg_resched_count": avg_count
                })

        df = pd.DataFrame(rows_data)
        if df.empty:
            continue

        sns.barplot(data=df, x="period_group", y="avg_resched_count", hue="network_size", ax=axs[idx])
        axs[idx].set_title(f"Avg Rescheduling Count ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Avg Reschedulings")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")
        if yaxis_bound is not None:
            axs[idx].set_ylim((0, yaxis_bound))

    for j in range(idx + 1, len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

def plot_rescheduling_probability_by_period_group(data, nw_sz):
    grouped_resched = defaultdict(float)
    grouped_success = defaultdict(int)

    for entry in data:
        rescheds = entry.get("resched_count_per_device_period", [])
        successes = entry.get("successful_txs_per_device_period", [])
        version = entry["version"]
        net_size = entry["network_size"]
        if net_size not in nw_sz:
            continue

        for i in range(min(len(rescheds), len(successes))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_resched[key] += rescheds[i]
            grouped_success[key] += successes[i]

    desired_order = ["Random", "Next Slot", "Optimized V1", "Optimized V2"]
    versions_in_data = [v for v in desired_order if any(k[0] == v for k in grouped_resched)]
    period_groups = [f"{g}-{g+9}" for g in range(20, 70, 10)] + ["70-70"]
    hue_order = sorted(set(nw_sz))

    cols = 2
    rows = math.ceil(len(versions_in_data) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=True)
    axs = axs.flatten()

    for idx, version in enumerate(versions_in_data):
        rows_data = []
        for period_group, net_size in product(period_groups, hue_order):
            key = (version, net_size, period_group)
            total_resched = grouped_resched.get(key, 0.0)
            total_success = grouped_success.get(key, 0)
            resched_prob = total_resched / total_success if total_success > 0 else 0

            rows_data.append({
                "network_size": net_size,
                "period_group": period_group,
                "resched_probability": resched_prob
            })

        df = pd.DataFrame(rows_data)

        sns.barplot(data=df, x="period_group", y="resched_probability", hue="network_size", hue_order=hue_order, ax=axs[idx])
        axs[idx].set_title(f"Rescheduling Probability ({version})")
        axs[idx].set_ylim((0,1.03))
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Probability of Rescheduling")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")

    for j in range(len(versions_in_data), len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()


def plot_data_unavailability_by_period_group(data, nw_sz, yaxis_bound=None):
    grouped_unavailable = defaultdict(int)
    grouped_total = defaultdict(int)

    for entry in data:
        shifts_per_device = entry.get("all_resched_shifts_per_device", [])
        periods = entry.get("device_periods", [])
        version = entry["version"]
        net_size = entry["network_size"]

        if net_size not in nw_sz:
            continue

        for i in range(min(len(shifts_per_device), len(periods))):
            period = periods[i]
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            shifts = shifts_per_device[i]
            grouped_total[key] += len(shifts)
            grouped_unavailable[key] += sum(1 for s in shifts if s > period)

    desired_order = ["Random", "Next Slot", "Optimized V1", "Optimized V2"]
    versions_in_data = [v for v in desired_order if any(k[0] == v for k in grouped_total)]
    period_groups = [f"{g}-{g+9}" for g in range(20, 70, 10)] + ["70-70"]
    hue_order = sorted(set(nw_sz))

    cols = 2
    rows = math.ceil(len(versions_in_data) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=True)
    axs = axs.flatten()

    for idx, version in enumerate(versions_in_data):
        rows_data = []
        for period_group, net_size in product(period_groups, hue_order):
            key = (version, net_size, period_group)
            total = grouped_total.get(key, 0)
            unavailable = grouped_unavailable.get(key, 0)
            rows_data.append({
                "network_size": net_size,
                "period_group": period_group,
                "unavailable_count": unavailable,
                "availability_ratio": 1 - (unavailable / total) if total > 0 else 1.0
            })

        df = pd.DataFrame(rows_data)

        sns.barplot(data=df, x="period_group", y="unavailable_count", hue="network_size", hue_order=hue_order, ax=axs[idx])
        axs[idx].set_yscale("log")
        axs[idx].set_ylim((-0.5,2750))
        axs[idx].set_title(f"Unavailable Transmissions ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Unavailable Shifts Count")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")

        if yaxis_bound is not None:
            axs[idx].set_ylim((0, yaxis_bound))

    for j in range(len(versions_in_data), len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

def plot_energy_by_period_group(data):
    grouped_energy = defaultdict(float)
    grouped_devices = defaultdict(int)

    for entry in data:
        version = entry.get("version")
        net_size = entry.get("network_size")

        energy_vals = entry.get("energy_per_device_period", [])
        device_counts = entry.get("devices_per_period", [])

        if not energy_vals or not device_counts:
            continue  # Skip incomplete data

        for i in range(min(len(energy_vals), len(device_counts))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_energy[key] += energy_vals[i]
            grouped_devices[key] += device_counts[i]

    # Construct DataFrame rows
    rows = []
    for (version, net_size, group_label), total_energy in grouped_energy.items():
        device_count = grouped_devices[(version, net_size, group_label)]
        if device_count > 0:
            avg_energy = total_energy / device_count
            rows.append({
                "version": version,
                "network_size": net_size,
                "period_group": group_label,
                "avg_energy": avg_energy
            })

    # Check if data exists
    if not rows:
        print("No data available for plotting.")
        return

    df = pd.DataFrame(rows)

    if not {"network_size", "avg_energy", "period_group", "version"}.issubset(df.columns):
        print("Missing expected columns in the DataFrame:", df.columns)
        return

    # Plot
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x="network_size", y="avg_energy", hue="period_group", style="version", marker="o")
    plt.title("Avg Energy Consumption per Period Group vs Network Size")
    plt.xlabel("Number of Devices")
    plt.ylabel("Avg Energy Consumption (J)")
    plt.legend(title="Period Group", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()


def plot_energy_efficiency_by_period_group(data, nw_sz, yaxis_bound=None):
    grouped_energy = defaultdict(float)
    grouped_success = defaultdict(int)

    for entry in data:
        energy = entry.get("energy_per_device_period", [])
        success = entry.get("successful_txs_per_device_period", [])
        version = entry["version"]
        net_size = entry["network_size"]
        if net_size not in nw_sz:
            continue

        for i in range(min(len(energy), len(success))):
            period = 20 + i
            if period > 70:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 70)}"
            key = (version, net_size, group_label)

            grouped_energy[key] += energy[i]
            grouped_success[key] += success[i]

    desired_order = ["Random", "Next Slot", "Optimized V1", "Optimized V2"]
    versions_in_data = [v for v in desired_order if any(k[0] == v for k in grouped_energy)]
    period_groups = [f"{g}-{g+9}" for g in range(20, 70, 10)] + ["70-70"]
    hue_order = sorted(set(nw_sz))

    cols = 2
    rows = math.ceil(len(versions_in_data) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(14, 5 * rows), sharex=True)
    axs = axs.flatten()

    for idx, version in enumerate(versions_in_data):
        rows_data = []
        for period_group, net_size in product(period_groups, hue_order):
            key = (version, net_size, period_group)
            total_success = grouped_success.get(key, 0)
            total_energy = grouped_energy.get(key, 0.0)
            avg_energy_per_tx = total_energy / total_success if total_success > 0 else 0

            rows_data.append({
                "network_size": net_size,
                "period_group": period_group,
                "energy_per_tx": avg_energy_per_tx
            })

        df = pd.DataFrame(rows_data)

        sns.barplot(data=df, x="period_group", y="energy_per_tx", hue="network_size", hue_order=hue_order, ax=axs[idx])
        axs[idx].set_title(f"Energy per Successful Tx ({version})")
        axs[idx].set_ylim((0,1.08))
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Energy per Tx (J)")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")

        if yaxis_bound is not None:
            axs[idx].set_ylim((0, yaxis_bound))

    for j in range(len(versions_in_data), len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    plt.show()

# ----------- USAGE ----------------

# Replace these with your actual filenames and version names
files = [
    ("results/next_slot.jsonl", "Next Slot"),
    ("results/random.jsonl", "Random"),
    ("results/optimized_v1.jsonl", "Optimized V1"),
    ("results/optimized_v2.jsonl", "Optimized V2")
]

all_data = []
for file, name in files:
    all_data.extend(load_jsonl(file, version_name=name))

#network_sizes = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800, 3000, 3200, 3400, 3600]
network_sizes = [1600, 1800, 2000, 2200, 2400, 2600, 2800]
network_sizes_group_bar = [2000, 2200, 2400, 2600]


# Utilization
#plot_utilization(all_data, network_sizes)

# Average rescheduling shift
#plot_avg_shift(all_data, network_sizes)

# Average of all downlink communication. My favorite
#plot_avg_downlink(all_data, network_sizes)

plot_avg_downlink_v2(all_data, network_sizes)

# Average rescheduling shift. Grouped by device period (bars are missing since some networks sizes don't have any rescheduling)
#plot_avg_shift_by_period_group_bar(all_data, network_sizes_group_bar, yaxis_bound=1000)

# Average number of reschedulings. Grouped by device period
#plot_avg_resched_count_by_period_group_bar(all_data, network_sizes_group_bar, yaxis_bound=32)

# Number of reschedulings divided by the number of successful transmissions
#plot_rescheduling_probability_by_period_group(all_data, nw_sz=network_sizes_group_bar)

# Unavailable if shift is greater then threshold = one device period (Does not look good. Maybe make a table instead)
#plot_data_unavailability_by_period_group(all_data, nw_sz=network_sizes_group_bar)


#plot_energy_by_period_group(all_data)

# Energy per successful tx
plot_energy_efficiency_by_period_group(all_data, nw_sz=network_sizes_group_bar)

