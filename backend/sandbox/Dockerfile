FROM node:20-slim

WORKDIR /workspace

ENV NODE_ENV=development \
    NPM_CONFIG_UPDATE_NOTIFIER=false

# node:20-slim already has uid/gid 1000 (`node`). The runner binds as 1000:1000.
RUN chown -R node:node /workspace
USER node

CMD ["node", "--version"]
