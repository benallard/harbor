# AGENTS.md

## Setup commands
- Install dependencies: `poetry install`
- Start dev server: `poetry run python -m harbor`
- Run tests: `poetry run pytest`

## Code style
- Use Black for formatting
- Follow PEP 8
- Use type hints where possible

## Testing instructions
- Run `pytest` to execute all tests
- Tests are in the `tests/` folder
- Ensure all tests pass before committing

## Project overview
Harbor is a Flask-based proxy and routing service supporting multiple backends like Caddy, Envoy, Nginx, and Traefik. It manages services dynamically with a registry and dispatcher.

## Build and deployment
- Build: Use `poetry build` to create distribution packages if needed (no build step required for development)
- Deploy: Use the provided service files in `contrib/` for systemd or other init systems
- Configuration: Use a YAML config file, environment variables, or CLI arguments (see docs/configuration.md for details)

## Security considerations
- Validate all inputs in API endpoints
- Use HTTPS in production
- Monitor logs for unauthorized access

## PR instructions
- Title format: [feature/fix] Description
- Run tests and linting before submitting
- Update documentation if needed