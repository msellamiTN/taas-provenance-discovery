"""TaaS token broker — real OIDC/JWKS validation + opaque downscoped issuance.

Data-path authentication component (E6 / D2 / D10). Deliberately a separate
package from ``taas.studio``: the broker is a different deployable with its
own trust domain. ``ak_*`` control-plane keys are never accepted here.
"""
