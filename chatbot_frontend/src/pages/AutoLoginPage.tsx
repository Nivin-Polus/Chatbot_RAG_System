import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getAssetUrl } from '@/utils/assets';

interface AutoLoginResponse {
    access_token: string;
    token_type: string;
    role: string;
    username: string;
    user_id: string;
    website_id?: string;
    collection_id: string;
}

export default function AutoLoginPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const token = searchParams.get('token');

        if (!token) {
            setError('No login token provided.');
            setIsLoading(false);
            return;
        }

        const validateAndLogin = async () => {
            try {
                const response = await fetch(
                    `${import.meta.env.VITE_API_BASE_URL}/auth/validate-auto-login`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ token }),
                    }
                );

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || 'Auto-login failed. The link may have expired.');
                }

                const data: AutoLoginResponse = await response.json();

                // Store auth data in session storage (same as regular login)
                const authUser = {
                    access_token: data.access_token,
                    role: data.role,
                    username: data.username,
                    user_id: data.user_id,
                    website_id: data.website_id,
                    collection_id: data.collection_id,
                };

                sessionStorage.setItem('auth_user', JSON.stringify(authUser));

                // Use window.location.href instead of navigate() to force a full page reload
                // This ensures AuthContext re-reads the sessionStorage on mount
                window.location.href = '/chatbot/pluginuser/chat';
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Auto-login failed.');
                setIsLoading(false);
            }
        };

        validateAndLogin();
    }, [searchParams, navigate]);

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-gradient-subtle p-4">
                <Card className="w-full max-w-md shadow-lg">
                    <CardHeader className="space-y-1">
                        <div className="flex items-center justify-center mb-4">
                            <div className="h-12 w-12 rounded-full border border-logo flex items-center justify-center p-2">
                                <img
                                    src={getAssetUrl('leto.svg')}
                                    alt="Leto Logo"
                                    className="h-8 w-8 object-contain"
                                />
                            </div>
                        </div>
                        <CardTitle className="text-xl text-center">Signing you in...</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col items-center gap-4">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        <p className="text-muted-foreground text-center">
                            Please wait while we authenticate your session.
                        </p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-gradient-subtle p-4">
                <Card className="w-full max-w-md shadow-lg">
                    <CardHeader className="space-y-1">
                        <div className="flex items-center justify-center mb-4">
                            <div className="h-12 w-12 rounded-full border border-destructive/50 flex items-center justify-center">
                                <AlertCircle className="h-6 w-6 text-destructive" />
                            </div>
                        </div>
                        <CardTitle className="text-xl text-center text-destructive">Login Failed</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col items-center gap-4">
                        <p className="text-muted-foreground text-center">{error}</p>
                        <Button onClick={() => navigate('/login')} variant="outline">
                            Go to Login Page
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return null;
}
