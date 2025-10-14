import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, Download, Trash2, Search, Loader2 } from 'lucide-react';
import { apiUpload } from '@/utils/api';
import { Collection, FileItem } from '@/types/auth';
import { toast } from 'sonner';

export default function SuperadminFiles() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, 'pending' | 'success' | 'error'>>({});

  useEffect(() => {
    fetchCollections();
  }, []);

  useEffect(() => {
    if (selectedCollection) {
      fetchFiles(selectedCollection);
    }
  }, [selectedCollection]);

  const fetchCollections = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/collections/`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setCollections(data);
      }
    } catch (error) {
      toast.error('Failed to fetch collections');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFiles = async (collectionId: string) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${collectionId}`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setFiles(data);
      }
    } catch (error) {
      toast.error('Failed to fetch files');
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0 || !selectedCollection) return;

    const filesArray = Array.from(selectedFiles);
    const allowedTypes = [
      'application/pdf',
      'text/plain',
      'text/csv',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ];
    const allowedExtensions = ['pdf', 'txt', 'csv', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    for (const file of filesArray) {
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      const isAllowedType = file.type ? allowedTypes.includes(file.type) : false;
      const isAllowedExtension = fileExtension ? allowedExtensions.includes(fileExtension) : false;

      if (!isAllowedType && !isAllowedExtension) {
        toast.error(`Invalid file type for ${file.name}. Allowed types: PDF, TXT, CSV, DOC/DOCX, PPT/PPTX, XLS/XLSX`);
        return;
      }
      if (file.size > maxSize) {
        toast.error(`File ${file.name} is too large. Maximum size: 10MB`);
        return;
      }
    }

    setUploading(true);
    const initialProgress: Record<string, 'pending' | 'success' | 'error'> = {};
    filesArray.forEach((file) => {
      initialProgress[file.name] = 'pending';
    });
    setUploadProgress(initialProgress);

    const formData = new FormData();
    filesArray.forEach((file) => {
      formData.append('uploaded_files', file);
    });
    formData.append('collection_id', selectedCollection);

    try {
      const response = await apiUpload(
        `${import.meta.env.VITE_API_BASE_URL}/files/upload`,
        formData,
        user?.access_token
      );

      if (!response.ok) throw new Error('Failed to upload files');

      const uploadedFiles: FileItem[] = await response.json();
      const uploadedNames = new Set(uploadedFiles.map((f) => f.file_name));

      setUploadProgress((prev) => {
        const updated: Record<string, 'pending' | 'success' | 'error'> = {};
        Object.keys(prev).forEach((name) => {
          updated[name] = uploadedNames.has(name) ? 'success' : 'error';
        });
        return updated;
      });

      await fetchFiles(selectedCollection);

      toast.success(`Uploaded ${uploadedFiles.length}/${filesArray.length} file(s)`);
      event.target.value = '';
    } catch (error) {
      console.error('Failed to upload files', error);
      toast.error(error instanceof Error ? error.message : 'Failed to upload files');
      setUploadProgress((prev) => {
        const updated: Record<string, 'pending' | 'success' | 'error'> = {};
        Object.keys(prev).forEach((name) => {
          updated[name] = 'error';
        });
        return updated;
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (fileId: string, fileName: string) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/files/download/${fileId}`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const handleDelete = async (fileId: string) => {
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/files/${fileId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });

      if (response.ok) {
        toast.success('File deleted successfully');
        fetchFiles(selectedCollection);
      } else {
        throw new Error('Delete failed');
      }
    } catch (error) {
      toast.error('Failed to delete file');
    }
  };

  const filteredFiles = files.filter(file =>
    file.file_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Files Management</h1>
          <p className="text-muted-foreground">Upload and manage files for collections</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Select Knowledge Base</CardTitle>
            <CardDescription>Choose a knowledge base to manage its files</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-muted-foreground">Select Knowledge Base:</span>
                <Select value={selectedCollection} onValueChange={setSelectedCollection}>
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="Select a knowledge base" />
                  </SelectTrigger>
                  <SelectContent>
                    {collections.map((collection) => (
                      <SelectItem key={collection.collection_id} value={collection.collection_id}>
                        {collection.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {selectedCollection && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="h-5 w-5" />
                  Upload File
                </CardTitle>
                <CardDescription>
                  Upload files to the selected knowledge base (PDF, TXT, CSV, DOCX, PPTX, XLS/XLSX - Max 10MB)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-4">
                  <Label htmlFor="file-upload" className="sr-only">
                    Upload file
                  </Label>
                  <Input
                    id="file-upload"
                    type="file"
                    accept=".pdf,.txt,.csv,.docx,.pptx,.xls,.xlsx"
                    multiple
                    onChange={handleFileUpload}
                    disabled={uploading}
                    className="w-64"
                  />
                  {uploading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading...
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Files</CardTitle>
                <CardDescription>
                  {files.length} file(s) in this knowledge base
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-4 mb-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search files..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 w-64"
                    />
                  </div>
                </div>

                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : filteredFiles.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {searchTerm ? 'No files found matching your search.' : 'No files in this knowledge base yet.'}
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Uploaded</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredFiles.map((file) => (
                        <TableRow key={file.file_id}>
                          <TableCell className="font-medium">{file.file_name}</TableCell>
                          <TableCell>{formatFileSize(file.file_size)}</TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              file.processing_status === 'completed'
                                ? 'bg-green-100 text-green-800'
                                : file.processing_status === 'processing'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {file.processing_status}
                            </span>
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {new Date(file.upload_timestamp).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-right space-x-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDownload(file.file_id, file.file_name)}
                              disabled={file.processing_status !== 'completed'}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(file.file_id)}
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
