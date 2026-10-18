FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

COPY agent/agent.py agent/footnote.py agent/prep.py agent/README.md /app/agent/
COPY data/company_pack.json /app/data/company_pack.json

WORKDIR /app/agent
CMD ["python", "agent.py"]
