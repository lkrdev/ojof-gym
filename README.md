# ojof-gym

LookML patterns and examples for Outer Join On False (OJOF) multi-fact explores.

## Validation with Spectacles

This project uses [Spectacles](https://spectacles.dev) for LookML and SQL validation. No local installation or project dependencies are required; use `uvx` with your environment variables.

### Setup

Create a `.env` file in the project root:

```env
LOOKER_BASE_URL=https://your-looker-instance.cloud.looker.com
LOOKER_CLIENT_ID=your_client_id
LOOKER_CLIENT_SECRET=your_client_secret
LOOKER_PROJECT=your_project_name
```

### Commands

```bash
# Test connection
uvx --env-file .env spectacles connect

# Validate LookML syntax
uvx --env-file .env spectacles lookml

# Validate SQL queries against the warehouse
uvx --env-file .env spectacles sql

# Run Looker data tests
uvx --env-file .env spectacles assert
```
