import requests

def add_flow(fromIP='172.18.0.3', toIP='172.18.0.4'):

    data = {
        "dpid": 1152921504606846977,
        "cookie": 0,
        "cookie_mask": 0,
        "table_id": 0,
        "idle_timeout": 0,
        "hard_timeout": 0,
        "priority": 1,
        "flags": 0,
        "match": {
            "ipv4_dst": fromIP,
            "eth_type": 2048
        },
        "actions": [
            {
                "type": "SET_FIELD",
                "field": "ipv4_dst",
                "value": toIP
            }
        ]
    }

    response = requests.post('http://localhost:8080/stats/flowentry/add', json=data)
    print(response.text)

if __name__ == '__main__':
    add_flow()
