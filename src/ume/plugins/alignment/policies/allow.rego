package ume

# Allow an event only when no deny rules match and user consent is present

default allow = false

allow {
    input.consent
    not forbidden_node
    not admin_role_update
    not admin_edge
}
