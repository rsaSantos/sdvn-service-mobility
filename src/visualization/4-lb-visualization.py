import json
import matplotlib.pyplot as plt

# Function to read the data from a file
def read_data_from_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

# Load the structure from file (replace 'data.json' with the actual file path)
file_path = 'visualization.json'  # Path to the JSON file
data = read_data_from_file(file_path)

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

# Plot the data
plt.figure(figsize=(10, 6))
for node, loads in node_loads.items():
    plt.plot(times, loads, marker='o', label=node)  # Plot each node's loads over time

# Add titles and labels
plt.title('Node Load over Time')
plt.xlabel('Time')
plt.ylabel('Load')
plt.legend(title="Nodes")
plt.grid(True)

# Show the plot
plt.show()
