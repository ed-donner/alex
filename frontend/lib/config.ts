// API configuration that works for both local and production environments
export const getApiUrl = () => {
  // If explicitly provided, always use it (useful for S3-only deployments)
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;

  // In production (static export), use relative path which CloudFront will route to API Gateway
  // In development, use localhost:8000
  if (typeof window !== 'undefined') {
    // Client-side: check if we're on localhost
    if (window.location.hostname === 'localhost') {
      return 'http://localhost:8000';
    } else {
      // Production: use relative path (CloudFront handles routing /api/* to API Gateway)
      return '';
    }
  }
  // Server-side during build
  return '';
};

export const API_URL = getApiUrl();