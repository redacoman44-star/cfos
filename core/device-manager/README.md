# CFOS device-manager

Status: interface/design scaffold only; no daemon is implemented in Base v0.1.

Requirements:
- D-Bus API with versioned interfaces.
- Structured logs through journald and /var/log/cfos where appropriate.
- Least-privilege execution; privileged actions mediated by polkit.
- Unit and integration tests before enabling the service by default.
