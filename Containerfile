FROM registry.access.redhat.com/ubi10/python-312-minimal@sha256:3707d38fb29c496d184e85b63a9ec2d1678bcb5086e5dab00540d6eeaa7951a7

WORKDIR /
# OpenShift preflight check requires licensing files under /licenses
COPY licenses/ licenses

WORKDIR /opt/app-root/src

USER 0
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir uv

USER 1001

COPY --chown=1001:0 pyproject.toml uv.lock README.md ./
COPY --chown=1001:0 src ./src

RUN uv sync --frozen --no-dev

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
