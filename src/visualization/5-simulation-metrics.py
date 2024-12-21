import pandas as pd
import json
import os

# Example function to compute the metrics for a single simulation
def compute_metrics(data):
    times = sorted(map(int, data.keys()))
    all_latencies = []

    for t in times:
        all_latencies.extend(data[str(t)].values())  # Collect all latencies at time t

    avg_latency = sum(all_latencies) / len(all_latencies)
    min_latency = min(all_latencies)
    max_latency = max(all_latencies)
    std_dev = pd.Series(all_latencies).std()
    median_latency = pd.Series(all_latencies).median()
    latency_range = max_latency - min_latency

    # Find time to reach the minimum latency
    time_to_min_latency = times[all_latencies.index(min_latency)]
    
    return {
        'Average Latency': avg_latency,
        'Min Latency': min_latency,
        'Time to Min Latency': time_to_min_latency,
        'Max Latency': max_latency,
        'Std Dev': std_dev,
        'Median Latency': median_latency,
        'Latency Range': latency_range
    }

# Assuming you have multiple simulation files
simulation_files = os.listdir('Data')

# Create a DataFrame to hold the results
results = []

for sim_file in simulation_files:
    with open(f'Data/{sim_file}', 'r') as f:
        data = json.load(f)
        metrics = compute_metrics(data)
        metrics['Simulation'] = sim_file  # Add simulation name
        results.append(metrics)

# Create a DataFrame from the results
df = pd.DataFrame(results)

# Display the table
print(df)

# Optionally, save to CSV
df.to_csv('simulation_comparison.csv', index=False)
