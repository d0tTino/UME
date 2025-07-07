from ume.integrations import MemGPT

if __name__ == "__main__":
    client = MemGPT()
    client.send_events([
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}
    ])
    print(client.recall({"node_id": "n1"}))
