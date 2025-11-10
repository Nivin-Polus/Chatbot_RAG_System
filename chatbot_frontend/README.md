# Leto Admin Dashboard

A production-ready, multi-role admin dashboard built with React, TypeScript, and Tailwind CSS. Features role-based access control (RBAC), collection management, file handling, and AI-powered chat capabilities.

## 🎯 Overview

This application provides four distinct user roles with tailored dashboards:

- **Superadmin**: Global system management (collections, all users, system health)
- **Admin**: Collection-scoped management (files, prompts, users within their collection)
- **User Admin**: User management within a specific collection
- **Regular User**: View-only access to collections with chat capabilities

## 🏗️ Architecture

### Technology Stack

- **Frontend**: React 18 + TypeScript
- **Styling**: Tailwind CSS with custom design system
- **Routing**: React Router v6 with role-based guards
- **State Management**: React Context API + RxJS patterns
- **Data Fetching**: React Query (TanStack Query)
- **UI Components**: Shadcn/ui (Radix UI primitives)
- **Forms**: React Hook Form + Zod validation
- **Notifications**: Sonner (toast notifications)

### Project Structure

```
src/
├── components/
│   ├── ui/              # Shadcn UI components
│   ├── AppSidebar.tsx   # Main navigation sidebar
│   ├── DashboardLayout.tsx
│   └── ProtectedRoute.tsx
├── contexts/
│   └── AuthContext.tsx  # Authentication & session management
├── pages/
│   ├── superadmin/      # Superadmin dashboard pages
│   ├── admin/           # Admin dashboard pages
│   ├── useradmin/       # User Admin pages
│   ├── user/            # Regular user pages
│   ├── Login.tsx
│   └── AccessDenied.tsx
├── types/
│   └── auth.ts          # TypeScript interfaces
├── lib/
│   └── utils.ts         # Utility functions
└── App.tsx              # Root component with routing
```

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running (see API Integration section)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd leto-admin

# Install dependencies
npm install

# Set up environment variables (create .env.local)
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

# Start development server
npm run dev
```

The app will be available at `http://localhost:8080`

### Environment Variables

Create a `.env.local` file in the project root:

```env
VITE_API_BASE_URL=http://localhost:8000
```

**Note**: All environment variables must be prefixed with `VITE_` to be accessible in the application.

## 🔐 Authentication & Authorization

### Authentication Flow

1. User submits credentials via `/login`
2. Frontend sends POST to `/auth/token` with form-encoded data
3. Backend returns JWT access token
4. Frontend decodes JWT to extract: `role`, `user_id`, `website_id`, `collection_id`
5. Token and user data stored in `sessionStorage`
6. `Authorization: Bearer <token>` header attached to all subsequent requests

### Role-Based Routing

| Role | Route | Access |
|------|-------|--------|
| Superadmin | `/superadmin/*` | Global collections, users, system |
| Admin | `/admin/:collection_id/*` | Files, prompts, users in collection |
| User Admin | `/useradmin/:collection_id/*` | Users in collection only |
| Regular User | `/app/*` | View collections, chat |

### Route Guards

The `ProtectedRoute` component wraps role-specific routes:

```tsx
<ProtectedRoute allowedRoles={['superadmin']}>
  <SuperadminDashboard />
</ProtectedRoute>
```

Unauthorized users are redirected to `/access-denied`.

## 📊 Features by Role

### Superadmin Features

- ✅ **Collections Management**
  - Create, edit, delete collections
  - Auto-create admin user on collection creation
  - Paginated table view with search
  
- ✅ **Files Management** (per collection)
  - Upload/download/delete files
  - File type and size validation
  - Progress bar during upload
  
- ✅ **Prompts Management** (per collection)
  - CRUD operations on prompts
  - Set default prompt
  - Minimum 1 prompt enforced
  
- ✅ **User Management**
  - Create users with role assignment
  - Multi-collection assignment
  - Superadmin account cannot be deleted
  
- ✅ **Chat Interface**
  - Collection selector
  - Session/history support
  - Streaming responses (if backend supports)
  
- ✅ **System Settings**
  - Password reset for superadmin
  - System health monitoring

### Admin Features

- ✅ Scoped to their assigned collection
- ✅ Files, Prompts, Users management (collection-scoped)
- ✅ Chat with collection context
- ✅ Settings (change password)

### User Admin Features

- ✅ User management within their collection only
- ✅ Cannot modify collection settings

### Regular User Features

- ✅ View accessible collections
- ✅ Chat interface with collection selection
- ✅ Read-only file access

## 🌐 API Integration

### Base URL Configuration

Set the API base URL in `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

All API calls are prefixed with this URL. Example:

```typescript
fetch(`${import.meta.env.VITE_API_BASE_URL}/collections/`, {
  headers: {
    Authorization: `Bearer ${user.access_token}`
  }
})
```

### Endpoint Reference

#### Authentication
- `POST /auth/token` - Login (returns JWT)

#### Collections
- `GET /collections/` - List all collections
- `POST /collections/` - Create collection
- `PUT /collections/{id}` - Update collection
- `DELETE /collections/{id}` - Delete collection

#### Files
- `GET /files/list?collection_id={id}` - List files in collection
- `POST /files/upload` - Upload file (multipart/form-data)
- `GET /files/download/{id}` - Download file
- `DELETE /files/{id}` - Delete file

#### Prompts
- `GET /prompts/?collection_id={id}` - List prompts
- `POST /prompts/` - Create prompt
- `PUT /prompts/{id}` - Update prompt
- `DELETE /prompts/{id}` - Delete prompt

#### Users
- `GET /users/` - List users
- `POST /users/` - Create user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user
- `GET /users/me/accessible-files` - Get files accessible to current user
- `POST /users/reset-password` - Reset user password

#### Chat
- `POST /chat/ask` - Send chat message
  - Supports both JSON and streaming responses

#### Activity
- `GET /activity/recent?limit=50` - Recent activity
- `GET /activity/stats` - Activity statistics
- `DELETE /activity/reset-files` - Reset file activity
- `DELETE /activity/reset-all` - Reset all activity

#### System Health
- `GET /health` - Health check
- `POST /health/reset` - Reset health data
- `GET /system/stats/overview` - System overview
- `GET /system/health/detailed` - Detailed health metrics

### API Mismatch Tracking

See `api-mismatch.md` for detailed tracking of:
- Expected vs. actual API responses
- Frontend model adaptations
- Integration status per endpoint

## 🎨 Design System

### Color Palette

The design system uses HSL colors for full theme support:

**Light Mode**:
- Primary: Deep Indigo (`hsl(239 84% 67%)`)
- Accent: Cyan (`hsl(189 94% 43%)`)
- Background: Light Gray (`hsl(220 18% 97%)`)

**Dark Mode**:
- Primary: Indigo (`hsl(239 84% 67%)`)
- Accent: Cyan (`hsl(189 94% 43%)`)
- Background: Dark Slate (`hsl(222 47% 11%)`)

### Typography

- **Headings**: System font stack (optimized for each OS)
- **Body**: Clean sans-serif with clear hierarchy
- **Code**: Monospace for technical content

### Animations

- **Fade In**: `animate-fade-in` (0.3s ease-out)
- **Scale In**: `animate-scale-in` (0.2s ease-out)
- **Slide In**: `animate-slide-in` (0.3s ease-out)
- **Glow**: `animate-glow` (2s infinite)

### Responsive Design

- **Mobile First**: Base styles optimized for mobile
- **Breakpoints**:
  - `sm`: 640px
  - `md`: 768px (tablet)
  - `lg`: 1024px (desktop)
  - `xl`: 1280px
  - `2xl`: 1400px (max container width)

## 🧪 Testing

### Unit Tests

**Framework**: Vitest + React Testing Library

**Coverage**:
- ✅ AuthService/AuthContext
- ✅ CollectionsService
- ✅ ChatService
- ✅ AuthGuard/ProtectedRoute

**Run tests**:
```bash
npm run test
npm run test:coverage
```

### E2E Tests

**Framework**: Playwright

**Test Scenarios**:
1. Login flow → Dashboard navigation
2. Collections CRUD
3. File upload → Download
4. Chat interaction with streaming

**Run E2E tests**:
```bash
npm run test:e2e
npm run test:e2e:ui  # Interactive mode
```

### Test Report

See `test-report.md` for detailed test results and coverage metrics.

## 📋 Code Quality

### ESLint Configuration

```bash
# Run linter
npm run lint

# Auto-fix issues
npm run lint:fix
```

**Rules**:
- TypeScript strict mode enabled
- React Hooks rules enforced
- Unused variables flagged (warnings)

### Type Safety

- All components use TypeScript
- Strict null checks enabled
- No implicit `any` types
- Zod schemas for runtime validation

## 🔧 Build & Deployment

### Development

```bash
npm run dev  # Start dev server at :8080
```

### Production Build

```bash
npm run build       # Build to /dist
npm run preview     # Preview production build
```

### Build Output

```
dist/
├── assets/
│   ├── index-[hash].js    # Main bundle
│   ├── index-[hash].css   # Styles
│   └── vendor-[hash].js   # Dependencies
├── index.html
└── robots.txt
```

### Deployment Options

- **Static Hosting**: Vercel, Netlify, Cloudflare Pages
- **Docker**: See `Dockerfile` (if included)
- **CDN**: Upload `dist/` to S3 + CloudFront

**Environment Variables**: Remember to set `VITE_API_BASE_URL` in your hosting provider's environment settings.

## 🛡️ Security Considerations

### Current Implementation

- ✅ JWT tokens stored in `sessionStorage` (cleared on logout)
- ✅ Authorization header on all API requests
- ✅ Role-based route guards
- ✅ Input validation with Zod
- ✅ XSS protection via React (JSX escaping)

### Production Recommendations

- 🔒 **Token Refresh**: Implement refresh token flow
- 🔒 **HTTPS Only**: Enforce HTTPS in production
- 🔒 **CSP Headers**: Add Content-Security-Policy
- 🔒 **Rate Limiting**: Implement on backend
- 🔒 **JWT Verification**: Verify signature server-side (don't trust decoded payload)
- 🔒 **HttpOnly Cookies**: Consider using HttpOnly cookies instead of sessionStorage

## 📖 Additional Resources

- **Tailwind CSS**: https://tailwindcss.com/docs
- **Shadcn/ui**: https://ui.shadcn.com/
- **React Router**: https://reactrouter.com/
- **React Query**: https://tanstack.com/query/latest
- **Radix UI**: https://www.radix-ui.com/

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and commit: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/my-feature`
4. Open a Pull Request

### Branch Strategy

- `main`: Production-ready code
- `dev`: Development branch (default)
- `feature/*`: Feature branches
- `fix/*`: Bug fix branches

## 📝 License

[Specify your license here]

## 👥 Support

For issues or questions:
- GitHub Issues: [Your repo URL]
- Email: support@yourapp.com
- Documentation: [Docs URL]

---

**Last Updated**: 2025-01-02  
**Version**: 1.0.0  
**Status**: ✅ Production Ready (pending backend integration)
