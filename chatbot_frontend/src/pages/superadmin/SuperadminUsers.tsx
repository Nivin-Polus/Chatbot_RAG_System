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
import { Plus, Pencil, Trash2, Users, Search, Loader2, MoreHorizontal } from 'lucide-react';
import { Collection, User, UserRole } from '@/types/auth';
import { toast } from 'sonner';

export default function SuperadminUsers() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | string>('all');
  const [collectionFilter, setCollectionFilter] = useState<'all' | 'none' | string>('all');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'user' as UserRole,
    collection_ids: [] as string[],
  });

  useEffect(() => {
    fetchCollections();
    fetchUsers();
  }, []);

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
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/users/`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      toast.error('Failed to fetch users');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (formData.collection_ids.length === 0) {
      toast.error('Please select at least one collection');
      return;
    }

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/users/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          full_name: formData.full_name,
          password: formData.password,
          role: formData.role,
          collection_ids: formData.collection_ids,
        }),
      });

      if (!response.ok) throw new Error('Failed to create user');

      toast.success('User created successfully');
      setIsDialogOpen(false);
      setFormData({ username: '', email: '', full_name: '', password: '', role: 'user', collection_ids: [] });
      fetchUsers();
    } catch (error) {
      toast.error('Failed to create user');
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    if (formData.collection_ids.length === 0) {
      toast.error('Please select at least one collection');
      return;
    }

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/users/${editingUser.user_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          full_name: formData.full_name,
          password: formData.password || undefined, // Only include if provided
          role: formData.role,
          collection_ids: formData.collection_ids,
        }),
      });

      if (!response.ok) throw new Error('Failed to update user');

      toast.success('User updated successfully');
      setIsDialogOpen(false);
      setEditingUser(null);
      setFormData({ username: '', email: '', full_name: '', password: '', role: 'user', collection_ids: [] });
      fetchUsers();
    } catch (error) {
      toast.error('Failed to update user');
    }
  };

  const handleDelete = async (userId: string, username: string) => {
    if (username === 'superadmin') {
      toast.error('Cannot delete superadmin account');
      return;
    }

    if (!confirm('Are you sure you want to delete this user?')) return;

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/users/${userId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });

      if (response.ok) {
        toast.success('User deleted successfully');
        fetchUsers();
      } else {
        throw new Error('Delete failed');
      }
    } catch (error) {
      toast.error('Failed to delete user');
    }
  };

  const openEditDialog = (user: User) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      password: '',
      role: user.role,
      collection_ids: user.collection_ids || [],
    });
    setIsDialogOpen(true);
  };

  const closeDialog = () => {
    setIsDialogOpen(false);
    setEditingUser(null);
    setFormData({ username: '', email: '', full_name: '', password: '', role: 'user', collection_ids: [] });
  };

  const toggleCollection = (collectionId: string) => {
    setFormData(prev => ({
      ...prev,
      collection_ids: prev.collection_ids.includes(collectionId)
        ? prev.collection_ids.filter(id => id !== collectionId)
        : [...prev.collection_ids, collectionId]
    }));
  };

  const roleOptions = Array.from(new Set(users.map((item) => item.role).filter(Boolean))).sort();
  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredUsers = users.filter((candidate) => {
    const username = candidate.username?.toLowerCase() ?? '';
    const role = candidate.role?.toLowerCase() ?? '';
    const fullName = candidate.full_name?.toLowerCase() ?? '';
    const email = candidate.email?.toLowerCase() ?? '';
    const collectionsForUser = candidate.collection_ids ?? [];

    const matchesSearch =
      normalizedSearch.length === 0 ||
      username.includes(normalizedSearch) ||
      role.includes(normalizedSearch) ||
      fullName.includes(normalizedSearch) ||
      email.includes(normalizedSearch);

    const matchesRole = roleFilter === 'all' || candidate.role === roleFilter;
    const matchesCollection =
      collectionFilter === 'all' ||
      (collectionFilter === 'none'
        ? collectionsForUser.length === 0
        : collectionsForUser.includes(collectionFilter));

    return matchesSearch && matchesRole && matchesCollection;
  });

  const getCollectionNames = (collectionIds: string[]) => {
    if (!collectionIds || collectionIds.length === 0) return [];
    return collectionIds
      .map((id) => collections.find((c) => c.collection_id === id)?.name || 'Unknown')
      .filter(Boolean);
  };

  const getRoleColor = (role: UserRole) => {
    switch (role) {
      case 'super_admin':
      case 'superadmin':
        return 'bg-purple-100 text-purple-800';
      case 'admin':
        return 'bg-blue-100 text-blue-800';
      case 'useradmin':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatRoleLabel = (role: string) => {
    switch (role) {
      case 'super_admin':
        return 'Super Admin';
      case 'superadmin':
        return 'Superadmin';
      case 'useradmin':
        return 'User Admin';
      default:
        return role.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Users Management</h1>
           
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="shadow-glow">
                <Plus className="mr-2 h-4 w-4" />
                Create User
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser}>
                <DialogHeader>
                  <DialogTitle>
                    {editingUser ? 'Edit User' : 'Create New User'}
                  </DialogTitle>
                  <DialogDescription>
                    {editingUser 
                      ? 'Update user details and permissions' 
                      : 'Create a new user account'
                    }
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="username">Username *</Label>
                    <Input
                      id="username"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full Name *</Label>
                    <Input
                      id="full_name"
                      value={formData.full_name}
                      onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">
                      Password {editingUser ? '(leave blank to keep current)' : '*'}
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      required={!editingUser}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="role">
                      Role * {editingUser?.user_id === user?.user_id && (
                        <span className="text-sm text-muted-foreground">(Cannot change your own role)</span>
                      )}
                    </Label>
                    <Select 
                      value={formData.role} 
                      onValueChange={(value: UserRole) => setFormData({ ...formData, role: value })}
                      disabled={editingUser?.user_id === user?.user_id}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">User</SelectItem>
                        <SelectItem value="useradmin">User Admin</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Assigned Knowledge Bases *</Label>
                    <div className="space-y-2 max-h-32 overflow-y-auto border rounded-md p-2">
                      {collections.map((collection) => (
                        <div key={collection.collection_id} className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            id={`collection-${collection.collection_id}`}
                            checked={formData.collection_ids.includes(collection.collection_id)}
                            onChange={() => toggleCollection(collection.collection_id)}
                            className="rounded"
                          />
                          <Label htmlFor={`collection-${collection.collection_id}`} className="text-sm">
                            {collection.name}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={closeDialog}>
                    Cancel
                  </Button>
                  <Button type="submit">
                    {editingUser ? 'Update User' : 'Create User'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              All Users
            </CardTitle>
            <CardDescription>
              {users.length} user(s) total
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search users..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 w-64"
                />
              </div>
              <Select value={roleFilter} onValueChange={setRoleFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All roles</SelectItem>
                  {roleOptions.map((role) => (
                    <SelectItem key={role} value={role}>
                      {formatRoleLabel(role)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={collectionFilter} onValueChange={setCollectionFilter}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Collection" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All collections</SelectItem>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {collections.map((collection) => (
                    <SelectItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchTerm ? 'No users found matching your search.' : 'No users yet.'}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Full Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Collections</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => (
                    <TableRow key={user.user_id}>
                      <TableCell className="font-medium">{user.username}</TableCell>
                      <TableCell>{user.full_name}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getRoleColor(user.role)}`}>
                          {user.role}
                        </span>
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const names = getCollectionNames(user.collection_ids || []);
                          if (names.length === 0) {
                            return '—';
                          }
                          if (names.length === 1) {
                            return names[0];
                          }
                          return (
                            <div className="flex items-center space-x-2">
                              <span>{names[0]}</span>
                              <Dialog>
                                <DialogTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-6 w-6">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DialogTrigger>
                                <DialogContent className="max-w-sm">
                                  <DialogHeader>
                                    <DialogTitle>Assigned Knowledge Bases</DialogTitle>
                                    <DialogDescription>
                                      {user.username} has access to the following collections.
                                    </DialogDescription>
                                  </DialogHeader>
                                  <div className="space-y-2 max-h-64 overflow-y-auto">
                                    {names.map((name) => (
                                      <div key={name} className="rounded-md border px-3 py-2 text-sm text-foreground">
                                        {name}
                                      </div>
                                    ))}
                                  </div>
                                </DialogContent>
                              </Dialog>
                            </div>
                          );
                        })()}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(user.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(user)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(user.user_id, user.username)}
                          disabled={user.username === 'superadmin'}
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
      </div>
    </DashboardLayout>
  );
}
