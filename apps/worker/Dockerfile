FROM oven/bun:1

WORKDIR /app
COPY package.json ./
RUN bun install
COPY src ./src
EXPOSE 9000
CMD ["bun", "run", "start"]
