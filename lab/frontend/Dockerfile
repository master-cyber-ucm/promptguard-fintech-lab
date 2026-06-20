FROM node:20-slim

WORKDIR /app

RUN npm install -g pnpm

COPY package.json .
RUN pnpm install

COPY src/ ./src/

EXPOSE 3000

# http-server with SPA fallback: all unknown routes → index.html
# playground.html served directly
CMD ["npx", "http-server", "src", "-p", "3000", "-c-1", "--cors", "--proxy", "http://localhost:3000?"]
