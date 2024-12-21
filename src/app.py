#
# This module is responsible for launching the desired simulation, depending on the config file used.
#
import sys
import json

def main(kindCfg, mininetCfg, sdnController):

    if '1_POC_Replication' in kindCfg:
        print("Running POC Replication scenario...")
        from scenarios.POCReplication import POCReplication
        scenario = POCReplication(kindCfg, mininetCfg, sdnController)
        scenario.run()

    elif '2_POC_Migration' in kindCfg:
        print("Running POC Migration scenario...")
        from scenarios.POCMigration import POCMigration
        scenario = POCMigration(kindCfg, mininetCfg, sdnController)
        scenario.run()
    elif '3_StreamingService' in kindCfg:
        print("Running Streaming Service scenario...")
        from scenarios.StreamingService import StreamingService
        scenario = StreamingService(kindCfg, mininetCfg, sdnController)
        scenario.run()
    elif '4_LoadBalancing' in kindCfg:
        print("Running Load Balancing scenario...")
        from scenarios.LoadBalancing import LoadBalancing
        scenario = LoadBalancing(kindCfg, mininetCfg, sdnController)
        scenario.run()
    elif '5_MobilityStrategy' in kindCfg:
        print("Running Mobility Strategy scenario...")
        from scenarios.MobilityStrategy import MobilityStrategy
        scenario = MobilityStrategy(kindCfg, mininetCfg, sdnController)
        scenario.run()
    else:
        print(f"Invalid config file! Scenario not found.")
        sys.exit(1)

def configReader(configPath):
    # Check if the config file exists
    configPath = sys.argv[1]
    config_json = None
    try:
        with open(configPath, 'r') as file:
            print(f"Using config file: {configPath}")
            config_json = json.load(file)

    except FileNotFoundError:
        print(f"File '{configPath}' not found!")
        sys.exit(1)
    
    if config_json is None:
        print("Error reading the config file!")
        sys.exit(1)

    keys = ['kind-config', 'mininet-config', 'sdn-controller']
    for key in keys:
        if key not in config_json:
            print(f"Missing '{key}' in config file!")
            sys.exit(1)
    
    # Check if files exist
    for key in keys:
        try:
            filenames = config_json[key].split(' ')
            for filename in filenames:
                with open(filename, 'r') as file:
                    print(f"Using file: {filename}")
        except FileNotFoundError:
            print(f"File '{config_json[key]}' not found!")
            sys.exit(1)

    return config_json["kind-config"], config_json["mininet-config"], config_json["sdn-controller"]

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 app.py <config file path>")
        sys.exit(1)
    else:
        kindCfg, mininetnCfg, sdnController = configReader(sys.argv[1])
        main(kindCfg, mininetnCfg, sdnController)
