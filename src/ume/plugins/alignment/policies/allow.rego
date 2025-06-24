package ume

# Allow an event only when no deny rules match

default allow = false

allow {
    not forbidden_node
    not admin_role_update
    not admin_edge
}
