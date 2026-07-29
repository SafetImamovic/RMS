"""Track geometry and vehicle calibration for M2 (feature 003).

The statistical half of the Unity driving environment. Everything that needs proving
lives here, in Python, where pytest can exercise it in under a second; Unity reads the
JSON this package writes and places objects.

Modules:
    config      named constants, every one traced to a research decision
    vehicle     the VehicleProfile and the bicycle-model geometry around it

See specs/003-unity-environment/contracts/track-generator-api.md for the contract.
"""
