import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Pencil, Trash2, FileCode, Loader2 } from 'lucide-react';
import { Collection, Prompt } from '@/types/auth';
import { toast } from 'sonner';

export default function SuperadminPrompts() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    content: '',
    is_default: false,
  });

  useEffect(() => {
    fetchCollections();
  }, []);

  useEffect(() => {
    if (selectedCollection) {
      fetchPrompts(selectedCollection);
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

  const fetchPrompts = async (collectionId: string) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${collectionId}`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setPrompts(data);
      }
    } catch (error) {
      toast.error('Failed to fetch prompts');
    }
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCollection) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/prompts/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          name: formData.name,
          content: formData.content,
          is_default: formData.is_default,
          collection_id: selectedCollection,
        }),
      });

      if (!response.ok) throw new Error('Failed to create prompt');

      toast.success('Prompt created successfully');
      setIsDialogOpen(false);
      setFormData({ name: '', content: '', is_default: false });
      fetchPrompts(selectedCollection);
    } catch (error) {
      toast.error('Failed to create prompt');
    }
  };

  const handleUpdatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPrompt) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/prompts/${editingPrompt.prompt_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          name: formData.name,
          content: formData.content,
          is_default: formData.is_default,
        }),
      });

      if (!response.ok) throw new Error('Failed to update prompt');

      toast.success('Prompt updated successfully');
      setIsDialogOpen(false);
      setEditingPrompt(null);
      setFormData({ name: '', content: '', is_default: false });
      fetchPrompts(selectedCollection);
    } catch (error) {
      toast.error('Failed to update prompt');
    }
  };

  const handleDelete = async (promptId: string) => {
    if (prompts.length <= 1) {
      toast.error('Cannot delete the last prompt. At least one prompt must exist.');
      return;
    }

    if (!confirm('Are you sure you want to delete this prompt?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/prompts/${promptId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });

      if (response.ok) {
        toast.success('Prompt deleted successfully');
        fetchPrompts(selectedCollection);
      } else {
        throw new Error('Delete failed');
      }
    } catch (error) {
      toast.error('Failed to delete prompt');
    }
  };

  const openEditDialog = (prompt: Prompt) => {
    setEditingPrompt(prompt);
    setFormData({
      name: prompt.name,
      content: prompt.system_prompt,
      is_default: prompt.is_default,
    });
    setIsDialogOpen(true);
  };

  const closeDialog = () => {
    setIsDialogOpen(false);
    setEditingPrompt(null);
    setFormData({ name: '', content: '', is_default: false });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Prompts Management</h1>
            <p className="text-muted-foreground">Manage prompts for knowledge base</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Select Knowledge Base</CardTitle>
            <CardDescription>Choose a knowledge base to manage its prompts</CardDescription>
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
                  <FileCode className="h-5 w-5" />
                  Prompts
                </CardTitle>
                <CardDescription>
                  {prompts.length} prompt(s) in this knowledge base
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <div></div>
                  <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                      <Button className="shadow-glow">
                        <Plus className="mr-2 h-4 w-4" />
                        Create Prompt
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                      <form onSubmit={editingPrompt ? handleUpdatePrompt : handleCreatePrompt}>
                        <DialogHeader>
                          <DialogTitle>
                            {editingPrompt ? 'Edit Prompt' : 'Create New Prompt'}
                          </DialogTitle>
                          <DialogDescription>
                            {editingPrompt 
                              ? 'Update the prompt details' 
                              : 'Create a new prompt for the selected knowledge base'
                            }
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div className="space-y-2">
                            <Label htmlFor="name">Prompt Name *</Label>
                            <Input
                              id="name"
                              value={formData.name}
                              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                              required
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="content">Prompt Content *</Label>
                            <Textarea
                              id="content"
                              value={formData.content}
                              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                              rows={8}
                              required
                            />
                          </div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="is_default"
                              checked={formData.is_default}
                              onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
                            />
                            <Label htmlFor="is_default">Set as Default Prompt</Label>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button type="button" variant="outline" onClick={closeDialog}>
                            Cancel
                          </Button>
                          <Button type="submit">
                            {editingPrompt ? 'Update Prompt' : 'Create Prompt'}
                          </Button>
                        </DialogFooter>
                      </form>
                    </DialogContent>
                  </Dialog>
                </div>

                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : prompts.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No prompts in this knowledge base yet. Create your first one!
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Content Preview</TableHead>
                        <TableHead>Default</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {prompts.map((prompt) => (
                        <TableRow key={prompt.prompt_id}>
                          <TableCell className="font-medium">{prompt.name}</TableCell>
                          <TableCell className="text-muted-foreground max-w-xs truncate">
                            {prompt.system_prompt.length > 100 
                              ? `${prompt.system_prompt.substring(0, 100)}...` 
                              : prompt.system_prompt
                            }
                          </TableCell>
                          <TableCell>
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                prompt.is_default
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-gray-100 text-gray-800'
                              }`}
                            >
                              {prompt.is_default ? 'Default' : '—'}
                            </span>
                          </TableCell>
                          <TableCell className="text-right space-x-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => openEditDialog(prompt)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(prompt.prompt_id)}
                              disabled={prompts.length <= 1}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
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
