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

def group_indexed_data(entries, value_key, device_key, group_range=(20, 100), step=10):
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

def group_indexed_data_per_version(entries, value_key, device_key, group_range=(20, 100), step=10):
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

def plot_utilization(data):
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
def plot_avg_shift(data):
    rows = []
    for entry in data:
        avg_shift = entry["rescheduling_shift_sum"] / max(1, entry["network_size"])
        rows.append({
            "version": entry["version"],
            "network_size": entry["network_size"],
            "avg_shift": avg_shift
        })
    df = pd.DataFrame(rows)
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df, x="network_size", y="avg_shift", hue="version", marker="o")
    plt.title("Average Rescheduling Shift vs Number of Devices")
    plt.xlabel("Number of Devices")
    plt.ylabel("Avg Rescheduling Shift (min periods)")
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
            if period > 100:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 100)}"
            key = (version, net_size, group_label)

            grouped_shift[key] += values[i]
            grouped_devices[key] += devices[i]

    # Prepare data
    versions = sorted(set(k[0] for k in grouped_shift.keys()))
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
                    "avg_shift": avg_shift
                })

        df = pd.DataFrame(rows_data)
        if df.empty:
            continue

        sns.lineplot(data=df, x="period_group", y="avg_shift", hue="network_size", marker="o", ax=axs[idx])
        axs[idx].set_title(f"Avg Rescheduling Shift ({version})")
        axs[idx].set_xlabel("Device Period Group (min periods)")
        axs[idx].set_ylabel("Avg Shift (min periods)")
        axs[idx].tick_params(axis='x', rotation=45)
        axs[idx].legend(title="Network Size", bbox_to_anchor=(1.05, 1), loc="upper left")
        if not yaxis_bound == None:
            axs[idx].set_ylim((-1,yaxis_bound))

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
            if period > 100:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 100)}"
            key = (version, net_size, group_label)

            grouped_count[key] += values[i]
            grouped_devices[key] += devices[i]

    # Prepare data
    versions = sorted(set(k[0] for k in grouped_count.keys()))
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

# Is it actually the correct normalization? 
'''def plot_energy_by_period_group(data):
    grouped = group_indexed_data(data, "energy_per_device_period", "device_per_period")
    rows = []
    for (version, net_size, group_label), vals in grouped.items():
        rows.append({
            "version": version,
            "network_size": net_size,
            "period_group": group_label,
            "avg_energy": sum(vals) / len(vals)
        })

    df = pd.DataFrame(rows)
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x="network_size", y="avg_energy", hue="period_group", style="version", marker="o")
    plt.title("Avg Energy Consumption per Period Group vs Network Size")
    plt.xlabel("Number of Devices")
    plt.ylabel("Avg Energy Consumption (J)")
    plt.legend(title="Period Group", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()'''

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
            if period > 100:
                continue
            group_start = (period // 10) * 10
            group_label = f"{group_start}-{min(group_start + 9, 100)}"
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

# Plot 1
plot_utilization(all_data)

# Plot 2
plot_avg_shift(all_data)

# TODO: Make plot with average number of rescheduling

# Plot 3A
#plot_avg_shift_by_period_group(all_data, yaxis_bound=None)
plot_avg_shift_by_period_group(all_data, yaxis_bound=100)

# Plot 3B
#plot_avg_resched_count_by_period_group(all_data, yaxis_bound=None)
plot_avg_resched_count_by_period_group(all_data, yaxis_bound=21)

# Plot 4
plot_energy_by_period_group(all_data)
