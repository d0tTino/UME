from ume.integrations import LangGraph

if __name__ == "__main__":
    client = LangGraph()
    client.send_events([
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}
    ])
    print(client.recall({"node_id": "n1"}))
