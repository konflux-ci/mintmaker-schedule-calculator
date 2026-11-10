FROM registry.access.redhat.com/ubi10/python-312-minimal@sha256:b2ef6a758138574ee49e93ad9684da60fa88ef843541e31981099e607f7d1db1
# FROM registry.access.redhat.com/ubi9/python-312@sha256:19e1e927138b40454858f297884c2c4e2f13f5ba95b3f55faea174d3cbb57067

WORKDIR /
# OpenShift preflight check requires licensing files under /licenses
COPY licenses/ licenses

WORKDIR /opt/app-root/src

USER 0

RUN microdnf install -y gcc-c++ make python3.12-devel

COPY --chown=1001:0 pyproject.toml README.md requirements.txt ./
COPY --chown=1001:0 src ./src

USER 1001

RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps .

# Labels
LABEL name="Mintmaker Schedule Calculator"
LABEL description="Calculates the schedule for Mintmaker"
LABEL io.k8s.description="Mintmaker Schedule Calculator"
LABEL io.k8s.display-name="mintmaker-schedule-calculator"
LABEL summary="Mintmaker Schedule Calculator"
LABEL com.redhat.component="mintmaker-schedule-calculator"

CMD ["python", "-m", "mintmaker_schedule_calculator"]
