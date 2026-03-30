FROM python:3.11-slim
WORKDIR /
RUN pip install cron-converter
COPY schedules_calculator_script.py schedules_calculator_script.py
ENTRYPOINT ["python", "/schedules_calculator_script.py"]
