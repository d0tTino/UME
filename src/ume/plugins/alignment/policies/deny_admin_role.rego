package ume

# Deny updating a node role to "admin"

admin_role_update {
    input.event_type == "UPDATE_NODE_ATTRIBUTES"
    input.payload.attributes.role == "admin"
}
