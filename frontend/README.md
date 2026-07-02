# TripNegotiator Frontend

Modern, responsive Next.js frontend for the TripNegotiator multi-agent trip planning system.

## Features

- **Trip Request Form**: Submit trip preferences (destination, budget, interests, duration)
- **Negotiation Progress**: Real-time tracking of multi-agent negotiations across rounds
- **Trip History**: View past trip negotiations and results
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Real-time Polling**: Automatic updates as agents negotiate
- **Status Visualization**: Visual indicators for approved/rejected proposals

## Tech Stack

- **Next.js 14**: React framework with SSR/SSG
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Axios**: HTTP client for API calls

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.local.example .env.local
# Edit .env.local with your API Gateway endpoint

# Run development server
npm run dev

# Open http://localhost:3000
```

### Building for Production

```bash
# Build static export for S3
npm run build
npm run export

# Output is in 'out/' directory
```

## Environment Variables

Create `.env.local` with:

```
NEXT_PUBLIC_API_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/dev
NEXT_PUBLIC_COGNITO_CLIENT_ID=your-client-id
NEXT_PUBLIC_COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
NEXT_PUBLIC_COGNITO_REDIRECT_URI=https://your-cloudfront-domain
```

## Deployment to AWS S3 + CloudFront

### Step 1: Build

```bash
npm run build
npm run export
```

### Step 2: Upload to S3

```bash
aws s3 sync out/ s3://tripnegotiator-frontend/ --delete
```

### Step 3: Invalidate CloudFront Cache

```bash
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

## API Integration

Connects to the following endpoints:

- `POST /trips` - Submit new trip request
- `GET /trips/{id}` - Get trip details and negotiation history
- `GET /trips` - Get user's trip history

## Components

- **TripForm**: Collects user preferences
- **NegotiationProgress**: Displays real-time negotiation updates
- **TripHistory**: Shows past negotiations

## Real-time Updates

The app polls the API every 2 seconds while negotiation is in progress:

```typescript
const trip = await pollTripStatus(tripId, 2000, 300) // 2s interval, 5min max
```

## Next Steps

1. Update `.env.local` with your API Gateway endpoint (after Terraform deployment)
2. Test locally: `npm run dev`
3. Build for production: `npm run build && npm run export`
4. Deploy to S3: Follow deployment instructions above
5. Set up CloudFront distribution to serve from S3
