package ume

# Deny events when user consent is not present
no_consent {
    not input.consent
}
