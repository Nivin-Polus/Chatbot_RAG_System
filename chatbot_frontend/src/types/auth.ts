export type UserRole = 'super_admin' | 'superadmin' | 'admin' | 'useradmin' | 'user_admin' | 'user';

export interface AuthUser {
  access_token: string;
  role: UserRole;
  username: string;
  user_id?: string;
  website_id?: string;
  collection_id?: string;
  collection_ids?: string[];
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface Collection {
  collection_id: string;
  name: string;
  description?: string;
  website_url?: string;
  admin_email?: string;
  is_active: boolean;
  user_count?: number;
  prompt_count?: number;
  file_count?: number;
  created_at: string;
  updated_at?: string;
  website_urls?: string[];
}

export interface FileItem {
  file_id: string;
  file_name: string;
  uploaded_by: string;
  uploader_id: string;
  upload_timestamp: string;
  file_size: number;
  processing_status: string;
  collection_id: string;
}

export interface Prompt {
  prompt_id: string;
  name: string;
  description?: string;
  system_prompt: string;
  user_prompt_template?: string;
  context_template?: string;
  vector_db_id?: string;
  website_id?: string;
  collection_id?: string;
  is_active: boolean;
  is_default: boolean;
  model_name?: string;
  max_tokens?: number;
  temperature?: number;
  usage_count?: number;
  created_at?: string;
  updated_at?: string;
  last_used?: string;
  collection_name?: string;
  vector_db_name?: string;
  website_name?: string;
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  website_id?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  last_login?: string;
  collection_ids: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isGeneric?: boolean;
  sources?: any[];
}
