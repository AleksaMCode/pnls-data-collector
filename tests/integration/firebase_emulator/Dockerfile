# Firebase Realtime Database emulator for the integration tests (see tests/integration/containers.py).
# Google publishes no Docker image for the emulator: it is the firebase-tools npm package and needs Java.
# Node is copied from the official Node image, so no unpinned apt packages are installed.
FROM node:22-bookworm-slim AS node

FROM eclipse-temurin:21-jre-noble

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

# Bump to a newer firebase-tools release when needed; the emulator API used by the tests is stable.
ARG FIREBASE_TOOLS_VERSION=14.0.0

# The emulator JAR is downloaded at build time, so starting a test container needs no network.
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install --global "firebase-tools@${FIREBASE_TOOLS_VERSION}" \
    && npm cache clean --force \
    && firebase setup:emulators:database

WORKDIR /emulator
COPY firebase.json /emulator/firebase.json

EXPOSE 9000

# A project ID starting with `demo-` makes the emulator run offline, without a Firebase login.
CMD ["firebase", "emulators:start", "--only", "database", "--project", "demo-pnls"]
