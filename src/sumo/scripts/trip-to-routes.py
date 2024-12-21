import re

def transform_trip_to_vehicle(trip_line):
    # Extract the necessary attributes using regex
    trip_id = re.search(r'id="([^"]+)"', trip_line).group(1)
    depart = re.search(r'depart="([^"]+)"', trip_line).group(1)
    from_edge = re.search(r'from="([^"]+)"', trip_line).group(1)
    to_edge = re.search(r'to="([^"]+)"', trip_line).group(1)
    via_edges = re.search(r'via="([^"]+)"', trip_line).group(1)
    
    # Combine from, via, and to into a single route
    route_edges = f"{from_edge} {via_edges} {to_edge}"
    
    # Generate the vehicle line in the desired format
    vehicle_line = f'''<vehicle id="{trip_id}" depart="1.00">
   <route edges="{route_edges}" />
</vehicle>'''
    
    return vehicle_line


input_file = 'trips.trips.xml'
with open(input_file, "r") as f:
    for line in f:
        output_line = transform_trip_to_vehicle(line.strip())
        print(output_line)
