# RGM Frontend

This is the frontend component of the **RGM (Running Community Manager)** platform. 
It is a [Next.js](https://nextjs.org) application bootstrapped with `create-next-app`.

For the complete **User Manual** and system documentation, please see the [Root README.md](../README.md).

## Getting Started

First, ensure you have set up your `.env.local` based on `.env.example`.

Then, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Tech Stack
- **Framework**: Next.js (App Router)
- **Styling**: Tailwind CSS
- **Authentication**: Firebase Auth
- **Data Fetching**: Axios (communicates with the RGM FastAPI Backend)
- **Charts**: Recharts / ECharts (dynamically imported)

## Key Features
- Strava OAuth Integration
- Firebase Auth (Email/Password & Google)
- Dashboard & Dynamic Leaderboards
- AI Coach Integration (Renato Canova persona)
- Comprehensive User Profile & Goal Setting
