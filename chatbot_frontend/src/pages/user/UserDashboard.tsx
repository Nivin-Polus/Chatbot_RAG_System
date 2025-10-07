import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Database, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet } from '@/utils/api';

interface AccessibleFile {
  id: string;
  name: string;
  collection_name: string;
  size: number;
  uploaded_at: string;
}

export default function UserDashboard() {
  const { user } = useAuth();
  const [files, setFiles] = useState<AccessibleFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchAccessibleFiles();
  }, []);

  const fetchAccessibleFiles = async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/users/me/accessible-files`,
        user?.access_token
      );
      if (response.ok) {
        const data = await response.json();
        setFiles(data);
      }
    } catch (error) {
      toast.error('Failed to fetch accessible files');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">My Knowledge Bases</h1>
          <p className="text-muted-foreground">View knowledge bases you have access to</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Accessible Files
            </CardTitle>
            <CardDescription>
              Files from knowledge bases you can access
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : files.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No accessible files found
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {files.map((file) => (
                  <Card key={file.id} className="hover:shadow-md transition-shadow">
                    <CardHeader>
                      <CardTitle className="text-base">{file.name}</CardTitle>
                      <CardDescription>{file.collection_name}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-sm text-muted-foreground">
                        <p>Size: {(file.size / 1024).toFixed(2)} KB</p>
                        <p>Uploaded: {new Date(file.uploaded_at).toLocaleDateString()}</p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
