# Repository instructions

- Treat the Docker image label in `Dockerfile` as the deployable application version.
- For every user-facing feature, bug fix, or deployment/configuration change, increment `LABEL version="..."` before committing. Use semantic versioning and increment the patch component by default; use a minor or major increment when appropriate.
- Keep the FastAPI application version in `app/main.py` equal to the Docker image label.
- When adding another Dockerfile, give it a `version` label and update that label whenever its resulting image changes.
