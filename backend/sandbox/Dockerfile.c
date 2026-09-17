FROM gcc:13-bookworm

WORKDIR /workspace

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin learner \
    && chown -R learner:learner /workspace

USER learner

CMD ["cc", "--version"]
