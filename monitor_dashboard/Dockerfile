# Keep the Node version in sync with .nvmrc at the repository root.
FROM node:26.13-alpine

# The npm bundled in the base image ships libraries with known vulnerabilities (undici, brace-expansion).
# Pinned to a release that has the fixes. Bump or remove once the base image catches up.
RUN npm install -g npm@11.21.3

WORKDIR /app

COPY package*.json $WORKDIR
COPY package-lock.json $WORKDIR
RUN npm install

COPY . $WORKDIR

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
