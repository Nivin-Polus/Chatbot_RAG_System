export class AuthError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AuthError';
    }
}

export const handleAuthError = (error: any) => {
    if (error.status === 422) {
        throw new AuthError('Invalid credentials or token format');
    }
    if (error.status === 401) {
        throw new AuthError('Authentication failed');
    }
    throw new AuthError('An unexpected error occurred during authentication');
};
