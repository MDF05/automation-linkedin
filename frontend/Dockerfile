FROM node:20-alpine

WORKDIR /app

# Install dependencies (layer cache: copy package files first)
COPY package.json package-lock.json* ./
RUN npm install --frozen-lockfile

# Copy all source files
COPY . .

# Build the Next.js application
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
