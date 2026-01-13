# 🤖 RAG Chatbot Plugin

A modern, embeddable chatbot plugin that integrates with your RAG (Retrieval-Augmented Generation) backend. This plugin provides a sleek, floating chat interface that can be easily embedded into any website.

## ✨ Features

- **🔐 OAuth2 Authentication** - Secure token-based authentication with automatic refresh
- **💬 Real-time Chat** - Smooth chat interface with typing indicators
- **🕒 Chat History** - Save and manage multiple chat sessions
- **↔️ Expandable UI** - Toggle between compact and expanded view with history sidebar
- **🎨 Modern UI** - Beautiful, responsive design with animations and enhanced input styling
- **📱 Mobile Friendly** - Works seamlessly on desktop and mobile devices
- **🔒 Secure** - HTML escaping and proper error handling
- **⚡ Fast** - Optimized build with Rollup and minification
- **🎯 Easy Integration** - Simple script tag integration
- **⚙️ Configurable UI** - Customizable header title, welcome message, and input placeholder

## 🚀 Quick Start

### Prerequisites

- Node.js (v14 or higher)
- A running RAG backend with the following endpoints:
  - `POST /auth/token` - OAuth2 authentication
  - `POST /chat/ask` - Chat endpoint
  - `GET /auth/verify` - Token verification (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Nivin-Polus/Chatbot_RAG-Plugin.git
   cd Chatbot_RAG-Plugin
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure the plugin**
   
   Edit `src/config.js` to match your backend and customize the UI:
   ```javascript
   export const CONFIG = {
     apiBase: "http://10.199.100.54:8000", // Your backend URL
     auth: {
       username: "user",                    // Your API username
       password: "user123"                  // Your API password
     },
     ui: {
       headerTitle: "RAG Chat Assistant",   // Chat header title
       welcomeMessage: "Hello! I'm your RAG-powered assistant. Ask me anything about your uploaded documents!",
       inputPlaceholder: "Ask me about your documents..." // Input field placeholder
     }
   };
   ```
   
   **Important**: 
   - Update the `apiBase` URL to point to your actual backend server
   - Customize the `ui` section to match your brand and messaging

4. **Build the plugin**
   ```bash
   npm run build
   ```

5. **Integrate into your website**
   ```html
   <!DOCTYPE html>
   <html>
   <head>
     <link rel="stylesheet" href="dist/chatbot.css">
   </head>
   <body>
     <!-- Your website content -->
     
     <script src="dist/chatbot.min.js"></script>
   </body>
   </html>
   ```

## 🛠️ Development

### Project Structure

```
src/
├── index.js      # Main entry point and initialization
├── auth.js       # Authentication service (OAuth2)
├── chat.js       # Chat service for API communication
├── ui.js         # UI components and chat interface
├── config.js     # Configuration settings
└── styles.css    # Styling and animations

dist/
├── chatbot.min.js  # Compiled and minified JavaScript
└── chatbot.css     # Compiled and minified CSS
```

### Available Scripts

- `npm run build` - Build the plugin for production (creates `dist/chatbot.min.js` and `dist/chatbot.css`)
- `npm run watch` - Build and watch for changes during development (auto-rebuilds on file changes)
- `npm install` - Install all project dependencies
- `npm test` - Run tests (currently not implemented)

### Build and Run Instructions

#### For Development:
```bash
# Install dependencies
npm install

# Start development mode with auto-rebuild
npm run watch
```

#### For Production:
```bash
# Install dependencies (if not already done)
npm install

# Build the plugin for production
npm run build

# The built files will be available in:
# - dist/chatbot.min.js (minified JavaScript)
# - dist/chatbot.css (compiled CSS)
```

#### Testing the Plugin:
1. Create a simple HTML file to test the plugin:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot Plugin Test</title>
    <link rel="stylesheet" href="dist/chatbot.css">
</head>
<body>
    <h1>Test Page for RAG Chatbot Plugin</h1>
    <p>The chatbot should appear as a floating button in the bottom-right corner.</p>
    
    <script src="dist/chatbot.min.js"></script>
</body>
</html>
```

2. Open the HTML file in a web browser
3. Click the chat button (💬) to open the chat interface
4. Make sure your backend is running on the configured URL

### Git Workflow

#### Initial Setup:
```bash
# Clone the repository
git clone https://github.com/Nivin-Polus/Chatbot_RAG-Plugin.git
cd Chatbot_RAG-Plugin

# Install dependencies
npm install

# Configure your backend URL in src/config.js
# Update the apiBase, username, and password as needed
```

#### Development Workflow:
```bash
# Create a new feature branch
git checkout -b feature/your-feature-name

# Make your changes and test
npm run watch  # For development with auto-rebuild

# Build for production
npm run build

# Commit your changes
git add .
git commit -m "Add your feature description"

# Push to your branch
git push origin feature/your-feature-name
```

#### Files Ignored by Git:
- `node_modules/` - Dependencies (will be installed via npm)
- `dist/` - Built files (generated by build process)
- `.env*` - Environment files with sensitive data
- IDE and OS specific files

### Backend API Requirements

Your backend must implement these endpoints:

#### Authentication Endpoint
```
POST /auth/token
Content-Type: application/x-www-form-urlencoded

Body:
username=your_username&password=your_password&grant_type=password

Response:
{
  "access_token": "jwt_token_here",
  "token_type": "bearer"
}
```

#### Chat Endpoint
```
POST /chat/ask
Content-Type: application/json
Authorization: Bearer {access_token}

Body:
{
  "question": "User's question here"
}

Response:
{
  "answer": "AI response here"
}
```

#### Token Verification (Optional)
```
GET /auth/verify
Authorization: Bearer {access_token}

Response: 200 OK (if valid) or 401 Unauthorized (if invalid)
```

## 🎨 Customization

### UI Text Customization

The plugin now supports configurable UI text elements. Simply modify the `ui` section in your `config.js`:

```javascript
export const CONFIG = {
  // ... other config
  ui: {
    headerTitle: "My Custom Assistant",
    welcomeMessage: "Hi there! I'm here to help you with any questions about our documentation.",
    inputPlaceholder: "What would you like to know?"
  }
};
```

**Examples of customization:**
- **E-commerce**: `headerTitle: "Shopping Assistant"`, `welcomeMessage: "Hi! I can help you find products and answer questions about your order."`
- **Documentation**: `headerTitle: "Help Center"`, `welcomeMessage: "Welcome! Ask me anything about our documentation."`
- **Support**: `headerTitle: "Customer Support"`, `welcomeMessage: "Hello! I'm here to help with your support questions."`

### Styling

The plugin uses CSS custom properties for easy theming. You can override these in your own CSS:

```css
:root {
  --chatbot-primary-color: #2563eb;
  --chatbot-hover-color: #1d4ed8;
  --chatbot-background: #ffffff;
  --chatbot-text-color: #111111;
}
```

### Configuration Options

Modify `src/config.js` to customize:

```javascript
export const CONFIG = {
  apiBase: "https://your-api.com",  // Backend URL
  auth: {
    username: "api_user",           // API username
    password: "secure_password"     // API password
  },
  ui: {
    headerTitle: "Your Custom Title",           // Chat header title
    welcomeMessage: "Your custom welcome message!", // Welcome message text
    inputPlaceholder: "Type your message here..."   // Input placeholder text
  }
};
```

#### UI Customization Options:
- **headerTitle**: The title displayed in the chat header
- **welcomeMessage**: The initial greeting message shown to users
- **inputPlaceholder**: The placeholder text in the message input field

## 🔧 Features in Detail

### Authentication
- **Automatic Login**: Uses configured credentials for seamless authentication
- **Token Storage**: Stores JWT tokens in localStorage for persistence
- **Auto Refresh**: Automatically refreshes expired tokens
- **Secure**: Uses OAuth2 password grant flow with form data

### Chat Interface
- **Floating Button**: Unobtrusive chat toggle button
- **Typing Indicator**: Animated dots while AI is responding
- **Loading States**: Visual feedback during requests
- **Error Handling**: User-friendly error messages
- **Keyboard Support**: Enter key to send messages
- **Auto-scroll**: Automatically scrolls to latest messages

### User Experience
- **Configurable Welcome Message**: Customizable greeting when chat opens
- **Enhanced Input Design**: Larger, modern input field with focus states and rounded corners
- **Improved Button Styling**: Better visual feedback with hover animations
- **Input Validation**: Prevents empty messages
- **Character Limit**: 500 character limit for messages
- **Responsive Design**: Works on all screen sizes
- **Smooth Animations**: CSS transitions for better UX

## 🐛 Troubleshooting

### Common Issues

**422 Unprocessable Entity Error**
- Ensure your backend accepts `application/x-www-form-urlencoded` for `/auth/token`
- Check that username/password in config match backend expectations

**404 Not Found Error**
- Verify your backend has `/chat/ask` endpoint (not just `/chat`)
- Check that `apiBase` in config points to correct URL

**CORS Issues**
- Configure your backend to allow requests from your domain
- Add appropriate CORS headers for preflight requests

**Token Issues**
- Check that your backend returns `access_token` in response
- Verify JWT token format and expiration

### Debug Mode

For debugging, you can check browser console for detailed error messages. The plugin logs authentication and chat errors with specific details.

## 📝 License

This project is licensed under the ISC License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/Nivin-Polus/Chatbot_RAG-Plugin/issues) page
2. Create a new issue with detailed description
3. Include browser console errors if applicable

## 🔄 Changelog

### v1.2.0
- ✅ **NEW**: Chat History Management (local storage persistence)
- ✅ **NEW**: Expandable Chat Interface with Sidebar
- ✅ **NEW**: Multiple Session Support with Delete capability
- ✅ **NEW**: Settings and Expand buttons

### v1.1.0
- ✅ **NEW**: Configurable UI text (header title, welcome message, input placeholder)
- ✅ **NEW**: Enhanced input field design with modern styling
- ✅ **NEW**: Improved button styling with hover animations
- ✅ **NEW**: Better visual hierarchy and spacing
- ✅ **IMPROVED**: Focus states for better accessibility

### v1.0.0
- ✅ Initial release
- ✅ OAuth2 authentication
- ✅ Real-time chat interface
- ✅ Typing indicators
- ✅ Error handling
- ✅ Mobile responsive design
- ✅ Production-ready build system

---

Made with ❤️ for seamless RAG integration