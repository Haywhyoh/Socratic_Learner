FROM python:3.12-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Non-root learner user
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin learner \
    && chown -R learner:learner /workspace
USER learner

CMD ["python", "--version"]
