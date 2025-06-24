package ume

# Deny creating an edge from the admin node

admin_edge {
    input.event_type == "CREATE_EDGE"
    input.node_id == "admin"
}
