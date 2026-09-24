# Secrets Management

Application secrets such as API keys, database passwords, and private
credentials should not be hardcoded in source code.

Secrets should be stored in a dedicated secrets-management system.

Applications should retrieve secrets securely at runtime and avoid
writing secret values to logs.

Rotate secrets regularly and grant the minimum required permissions.
