FROM node:22-alpine

WORKDIR /app

COPY package*.json $WORKDIR
COPY package-lock.json $WORKDIR
RUN npm install

COPY . $WORKDIR

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
