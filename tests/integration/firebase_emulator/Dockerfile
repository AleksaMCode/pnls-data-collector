# Firebase Realtime Database and Authentication emulators for the integration tests
# (see tests/integration/containers.py).
# Google publishes no Docker image for the emulator: it is the firebase-tools npm package and needs Java.
# Node is copied from the official Node image, so no unpinned apt packages are installed.
# Keep its version in sync with .nvmrc at the repository root.
FROM node:26.13-bookworm-slim AS node

# Node needs libatomic, which the Java image lacks. It's collected here because its folder depends on
# the CPU architecture.
RUN mkdir /node-libs && cp -P /usr/lib/*-linux-gnu/libatomic.so.1* /node-libs/

FROM eclipse-temurin:21-jre-noble

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node /node-libs/ /usr/local/lib/
RUN ldconfig

# Bump to a newer firebase-tools release when needed; the emulator API used by the tests is stable.
ARG FIREBASE_TOOLS_VERSION=14.0.0

# The database emulator JAR is downloaded at build time, so starting a test container needs no network.
# The Authentication emulator is part of firebase-tools itself and needs no download.
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install --global "firebase-tools@${FIREBASE_TOOLS_VERSION}" \
    && npm cache clean --force \
    && firebase setup:emulators:database

WORKDIR /emulator
COPY firebase.json /emulator/firebase.json

EXPOSE 9000 9099

# A project ID starting with `demo-` makes the emulator run offline, without a Firebase login.
CMD ["firebase", "emulators:start", "--only", "database,auth", "--project", "demo-pnls"]
