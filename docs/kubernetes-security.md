# Kubernetes Security

Containers should run as non-root users whenever possible.

Kubernetes workloads should use resource limits to reduce the impact
of resource exhaustion.

Network policies can restrict which workloads are allowed to communicate
with each other.

Use image scanning and minimal base images to reduce attack surface.
