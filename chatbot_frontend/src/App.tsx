import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ThemeProvider } from "@/components/ThemeProvider";

// Pages
import Login from "./pages/Login";
import AccessDenied from "./pages/AccessDenied";
import NotFound from "./pages/NotFound";
import SuperadminDashboard from "./pages/superadmin/SuperadminDashboard";
import SuperadminFiles from "./pages/superadmin/SuperadminFiles";
import SuperadminPrompts from "./pages/superadmin/SuperadminPrompts";
import SuperadminUsers from "./pages/superadmin/SuperadminUsers";
import SuperadminChat from "./pages/superadmin/SuperadminChat";
import SuperadminActivity from "./pages/superadmin/SuperadminActivity";
import SuperadminSettings from "./pages/superadmin/SuperadminSettings";
import KnowledgeBaseDetails from "./pages/superadmin/KnowledgeBaseDetails";
import UserDashboard from "./pages/user/UserDashboard";
import UserChat from "./pages/user/UserChat";
import UserAdminDashboard from "./pages/useradmin/UserAdminDashboard";
import UserAdminChat from "./pages/useradmin/UserAdminChat";
import UserAdminSettings from "./pages/useradmin/UserAdminSettings";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider defaultTheme="light" storageKey="leto-ui-theme">
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthProvider>
            <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/access-denied" element={<AccessDenied />} />
            
            {/* Superadmin Routes */}
            <Route
              path="/superadmin/*"
              element={
                <ProtectedRoute allowedRoles={['super_admin', 'superadmin']}>
                  <Routes>
                    <Route index element={<SuperadminDashboard />} />
                    <Route path="knowledge-base/:id" element={<KnowledgeBaseDetails />} />
                    <Route path="files" element={<SuperadminFiles />} />
                    <Route path="prompts" element={<SuperadminPrompts />} />
                    <Route path="users" element={<SuperadminUsers />} />
                    <Route path="chat" element={<SuperadminChat />} />
                    <Route path="activity" element={<SuperadminActivity />} />
                    <Route path="settings" element={<SuperadminSettings />} />
                  </Routes>
                </ProtectedRoute>
              }
            />

            {/* User Admin Routes */}
            <Route
              path="/useradmin/*"
              element={
                <ProtectedRoute allowedRoles={['useradmin', 'user_admin']}>
                  <Routes>
                    <Route index element={<Navigate to="knowledge-base" replace />} />
*** End Patch
                    <Route path="users" element={<UserAdminDashboard />} />
                    <Route path="knowledge-base" element={<UserAdminDashboard />} />
                    <Route path="chat" element={<UserAdminChat />} />
                    <Route path="settings" element={<UserAdminSettings />} />
                  </Routes>
                </ProtectedRoute>
              }
            />

            {/* Regular User Routes */}
            <Route
              path="/app/*"
              element={
                <ProtectedRoute allowedRoles={['user']}>
                  <Routes>
                    <Route index element={<Navigate to="/app/chat" replace />} />
                    <Route path="chat" element={<UserChat />} />
                  </Routes>
                </ProtectedRoute>
              }
            />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
