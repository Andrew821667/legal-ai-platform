import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

const PRIVATE_PREFIXES = ['/login', '/register', '/dashboard', '/contracts']

export function middleware(request: NextRequest) {
  const response = NextResponse.next()

  if (PRIVATE_PREFIXES.some((prefix) => request.nextUrl.pathname.startsWith(prefix))) {
    response.headers.set('X-Robots-Tag', 'noindex, nofollow, noarchive')
  }

  return response
}

export const config = {
  matcher: ['/login/:path*', '/register/:path*', '/dashboard/:path*', '/contracts/:path*'],
}
