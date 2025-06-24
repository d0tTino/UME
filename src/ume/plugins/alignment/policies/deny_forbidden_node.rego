package ume

# Deny creating a node with id "forbidden"

forbidden_node {
    input.event_type == "CREATE_NODE"
    input.payload.node_id == "forbidden"
}
