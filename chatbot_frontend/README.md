# Knowledge Base Chatbot Frontend

## 🚀 Overview

A modern React-based frontend for the Knowledge Base Chatbot that provides an intuitive interface for document management and AI-powered conversations.

### ✨ Features
- 🔐 **Secure Authentication** - JWT-based login system
- 📁 **File Management** - Upload, view, and delete documents with drag-and-drop
- 💬 **Interactive Chat** - Real-time conversations with your knowledge base
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile devices
- 🎨 **Modern UI** - Beautiful gradient design with smooth animations
- ⚡ **Real-time Updates** - Live file list updates and chat responses
- 🛡️ **Error Handling** - Comprehensive error messages and validation

---

## 📁 Project Structure

```
src/
├── components/
│   ├── Login.js           # 🔐 Authentication component
│   ├── ChatWindow.js      # 💬 Chat interface with message history
│   └── FileUploader.js    # 📁 File management interface
├── api/
│   └── api.js            # 🌐 Axios HTTP client with JWT interceptors
├── App.js                # 🚀 Main application component
├── index.js              # 📍 React app entry point
└── styles.css            # 🎨 Global styles and responsive design
```

---

## 🛠️ Setup Instructions

### 1. Prerequisites
- Node.js 16+ and npm
- **Backend API running with Python 3.10** on port 8000

### 2. Installation

```bash
# Navigate to frontend directory
cd chatbot_frontend

# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at: **http://localhost:3000**

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the frontend root:

```env
# 🌐 Backend API Configuration
REACT_APP_API_URL=http://localhost:8000

# 🔧 Optional: Custom port for development
PORT=3000
```

### API Integration

The frontend automatically connects to the backend API. Ensure:

1. **Backend is running** on `http://localhost:8000`
2. **CORS is enabled** in the backend (already configured)
3. **JWT tokens** are handled automatically by the API client

---

## 🔑 Authentication Flow

### Login Process
1. **Enter credentials**: `admin` / `admin123`
2. **JWT token** is automatically stored in localStorage
3. **Token included** in all subsequent API requests
4. **Auto-logout** when token expires

### Token Management
- Tokens stored securely in localStorage
- Automatic inclusion in API request headers
- Manual logout clears stored tokens
- Token expiration handled gracefully

---

## 📁 File Management Features

### Upload Documents
- **Supported formats**: PDF, DOCX, PPTX, XLSX, TXT
- **File size limit**: 25MB (configurable in backend)
- **Progress indication** during upload
- **Automatic list refresh** after upload

### File Operations
- **View all files** with metadata (name, uploader)
- **Delete files** with confirmation dialog
- **Real-time updates** when files are added/removed
- **Error handling** for failed operations

---

## 💬 Chat Interface

### Features
- **Multi-line input** with Enter to send (Shift+Enter for new line)
- **Message history** with user/bot distinction
- **Dual-response format** - Summary and detailed answers
- **Expandable details** - "Show More Details" button for comprehensive answers
- **Loading indicators** while processing
- **Error messages** for failed requests
- **Welcome message** for new users

### Message Types
- **User messages**: Blue bubbles on the right
- **Bot responses**: Gray bubbles on the left with summary answers
- **Detailed answers**: Expandable sections with comprehensive information
- **Error messages**: Red bubbles for failed requests
- **Typing indicator**: Animated "Thinking..." message

---

## 🎨 UI/UX Features

### Design Elements
- **Gradient background** with modern color scheme
- **Card-based layout** with subtle shadows
- **Responsive grid** (desktop: 2-panel, mobile: stacked)
- **Smooth animations** and transitions
- **Professional typography** with proper hierarchy

### Interactive Elements
- **Hover effects** on buttons and cards
- **Loading states** for all async operations
- **Form validation** with visual feedback
- **Confirmation dialogs** for destructive actions

---

## 🔧 Configuration Changes Needed

### For Different Backend URLs

If your backend runs on a different URL, update:

1. **Environment file** (`.env`):
   ```env
   REACT_APP_API_URL=https://your-backend-domain.com
   ```

2. **API client** (`src/api/api.js`):
   ```javascript
   const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
   ```

### For Custom Authentication

To change login credentials or add user registration:

1. **Update backend** authentication endpoints
2. **Modify Login component** (`src/components/Login.js`)
3. **Add registration form** if needed

### For Additional File Types

To support more file formats:

1. **Update backend** `ALLOWED_FILE_TYPES` in `.env`
2. **Modify file input** accept attribute in `FileUploader.js`:
   ```javascript
   accept=".pdf,.docx,.pptx,.xlsx,.txt,.your-format"
   ```

### For Custom Styling

To change the appearance:

1. **Modify CSS variables** in `src/styles.css`:
   ```css
   :root {
     --primary-color: #your-color;
     --secondary-color: #your-color;
   }
   ```

2. **Update gradient backgrounds** and color schemes
3. **Customize component-specific styles**

---

## 📱 Responsive Breakpoints

### Desktop (1200px+)
- Two-panel layout (files left, chat right)
- Full-width header with logout button
- Optimal spacing and typography

### Tablet (768px - 1199px)
- Maintained two-panel layout
- Adjusted padding and spacing
- Touch-friendly button sizes

### Mobile (<768px)
- Single-column stacked layout
- Files panel above chat panel
- Compressed header design
- Mobile-optimized input controls

---

## 🔌 API Integration Details

### HTTP Client Configuration
```javascript
// Automatic JWT token inclusion
api.interceptors.request.use(config => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});
```

### Error Handling
- **401 Unauthorized**: Automatic logout and redirect to login
- **Network errors**: User-friendly error messages
- **Validation errors**: Display backend error details
- **Timeout handling**: Configurable request timeouts

---

## 🚨 Troubleshooting

### Common Issues

1. **"Network Error" or CORS Issues**
   ```bash
   # Ensure backend is running
   curl http://localhost:8000/health
   
   # Check CORS configuration in backend
   ```

2. **Login Fails**
   - Verify credentials: `admin` / `admin123`
   - Check backend authentication endpoint
   - Inspect browser network tab for errors

3. **File Upload Fails**
   - Check file size (max 25MB)
   - Verify file type is supported
   - Ensure JWT token is valid

4. **Chat Not Working**
   - Upload at least one document first
   - Check Qdrant vector database is running
   - Verify Claude API key in backend

### Debug Mode

Enable detailed logging:
```javascript
// In src/api/api.js
api.interceptors.response.use(
  response => {
    console.log('API Response:', response);
    return response;
  },
  error => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);
```

---

## 🚀 Development

### Available Scripts

```bash
# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test

# Eject from Create React App (irreversible)
npm run eject
```

### Code Structure

- **Components**: Functional components with React hooks
- **State management**: Local state with useState and useEffect
- **API calls**: Centralized in api.js with error handling
- **Styling**: CSS modules with responsive design

### Adding New Features

1. **Create component** in `src/components/`
2. **Add API endpoints** in `src/api/api.js`
3. **Update routing** in `App.js` if needed
4. **Add styles** in `styles.css`

---

## 📦 Dependencies

### Core Dependencies
```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "axios": "^1.6.0"
}
```

### Development Dependencies
```json
{
  "react-scripts": "5.0.1",
  "@testing-library/react": "^13.4.0",
  "@testing-library/jest-dom": "^5.16.4"
}
```

---

## 🔐 Security Considerations

### JWT Token Storage
- Tokens stored in localStorage (consider httpOnly cookies for production)
- Automatic token cleanup on logout
- Token expiration handling

### Input Validation
- File type validation on frontend and backend
- File size limits enforced
- XSS protection through React's built-in escaping

### HTTPS in Production
- Always use HTTPS in production
- Update API_URL to use https://
- Configure proper CORS origins

---

## 📝 Default Login

**Username**: `admin`  
**Password**: `admin123`

⚠️ **Change these credentials in production!**

---

## 🤝 Integration with Backend

### Required Backend Endpoints
- `POST /auth/token` - Authentication
- `POST /files/upload` - File upload
- `GET /files/list` - List files
- `DELETE /files/{id}` - Delete file
- `POST /chat/ask` - Chat with documents (returns summary + detailed answers)

### Backend Requirements
- CORS enabled for frontend domain
- JWT authentication configured
- File upload limits set appropriately
- Qdrant vector database running
- Claude API key configured

---

## 📈 Performance Optimization

### Production Build
```bash
npm run build
```

### Optimization Features
- Code splitting with React.lazy (can be added)
- Image optimization for assets
- CSS minification and bundling
- Service worker for caching (can be added)

### Monitoring
- Add error tracking (Sentry, LogRocket)
- Performance monitoring
- User analytics integration
