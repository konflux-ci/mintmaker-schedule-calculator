FROM registry.redhat.io/ubi9/python-312@sha256:f793a102147ffa00b45ccb88ae91d726c17ac2f7e70214eef0cbfdc32816ec01
WORKDIR /
# OpenShift preflight check requires licensing files under /licenses
COPY licenses/ licenses

WORKDIR /opt/app-root/src

USER 0
RUN source /tmp/hermeto.env && \
    pip install --no-cache-dir uv

USER 1001

COPY --chown=1001:0 pyproject.toml uv.lock README.md requirements.txt ./
COPY --chown=1001:0 src ./src

RUN uv venv && \
    uv pip install --offline --no-index \
      --find-links=/tmp/hermeto-output/deps/pip \
      --require-hashes \
      -r requirements.txt && \
    uv pip install --offline --no-index --no-deps \
      --find-links=/tmp/hermeto-output/deps/pip .

ENV VIRTUAL_ENV=/opt/app-root/src/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Labels
LABEL name="Mintmaker Schedule Calculator"
LABEL description="Calculates the schedule for Mintmaker"
LABEL io.k8s.description="Mintmaker Schedule Calculator"
LABEL io.k8s.display-name="mintmaker-schedule-calculator"
LABEL summary="Mintmaker Schedule Calculator"
LABEL com.redhat.component="mintmaker-schedule-calculator"

CMD ["python", "-m", "mintmaker_schedule_calculator"]
