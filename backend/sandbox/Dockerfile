# The image the grader runs student code in. One throwaway container is started from it per submission.

FROM python:3.14-slim

# Must match backend/requirements.txt and what Pyodide ships. deploy/run.sh reads it from requirements.txt.
ARG NUMPY_VERSION=2.4.4
RUN pip install --no-cache-dir "numpy==${NUMPY_VERSION}"

# An ordinary user with no home and no login shell. runner.py runs everything as this uid (10001).
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin grader
USER grader
WORKDIR /work
