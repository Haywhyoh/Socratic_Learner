FROM golang:1.22-bookworm

WORKDIR /workspace

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin learner \
    && chown -R learner:learner /workspace

USER learner
ENV GOFLAGS=-mod=mod \
    GOTOOLCHAIN=local

CMD ["go", "version"]
