FROM node:20-slim

WORKDIR /workspace

ENV NODE_ENV=development \
    NPM_CONFIG_UPDATE_NOTIFIER=false

# Non-root learner user
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin learner \
    && chown -R learner:learner /workspace
USER learner

CMD ["node", "--version"]
