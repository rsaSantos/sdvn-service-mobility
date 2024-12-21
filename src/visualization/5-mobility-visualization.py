import json
import matplotlib.pyplot as plt
import argparse

# Function to read the data from a file
def read_data_from_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

# Set up argument parsing to get the JSON file path from the command line
parser = argparse.ArgumentParser(description='Plot latency data from a JSON file.')
parser.add_argument('file_path', type=str, help='Path to the JSON file containing the latency data')
args = parser.parse_args()

# Load the structure from the provided file
data = read_data_from_file(args.file_path)

# Extract all unique node names from the data
all_nodes = set()
for time_point in data.values():
    all_nodes.update(time_point.keys())
all_nodes = sorted(all_nodes)  # Sort the node names

# Extract time points and initialize node loads with 0s
times = sorted(map(int, data.keys()))  # Get sorted time points as integers
node_loads = {node: [] for node in all_nodes}

# Populate the node loads, using 0 if a node is missing at a certain time
for t in times:
    t_str = str(t)  # Keys in the data dictionary are strings
    for node in all_nodes:
        load = data[t_str].get(node, 0)  # Get load or default to 0
        node_loads[node].append(load)

# Plot the data with fixed dimensions
plt.figure(figsize=(10, 6))  # Size can be adjusted based on desired display

# Plot each node's loads over time
for node, loads in node_loads.items():
    plt.plot(times, loads, marker='o', label=node)

# Add titles and labels
plt.title('Global Latency of the Simulation')
plt.xlabel('Time')
plt.ylabel('Latency')

# Fix the axes limits to ensure the same scale
plt.xlim(0, 400)  # Ensure x-axis is fixed based on time range
plt.ylim(0, 500)  # Fix y-axis from 0 to 500 as requested

# Grid and show the plot
plt.grid(True)
plt.show()
