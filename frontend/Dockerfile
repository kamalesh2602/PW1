FROM node:20-alpine

WORKDIR /app

# Copy package specifications and install dependencies using lockfile
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code
COPY . .

EXPOSE 5173

# Start Vite dev server bound to 0.0.0.0
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
