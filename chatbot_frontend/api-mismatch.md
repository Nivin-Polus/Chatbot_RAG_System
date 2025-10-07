# API Integration Mismatch Report

This document tracks discrepancies between the frontend implementation and actual backend API responses.

## Status: ⚠️ Pending Backend Verification

**Note:** This frontend application has been built according to the provided API specifications. The following endpoints need to be tested against the actual backend to verify compatibility.

## Authentication Endpoints

### POST /auth/token
- **Status:** ⏳ Not yet tested
- **Expected Request:**
  ```
  Content-Type: application/x-www-form-urlencoded
  username=<username>&password=<password>
  ```
- **Expected Response:**
  ```json
  {
    "access_token": "eyJ...",
    "token_type": "bearer"
  }
  ```
- **Frontend Assumptions:**
  - JWT payload contains: `role`, `user_id`, `website_id`, `collection_id`
  - Token can be decoded client-side (not recommended for production without signature verification)

## Collections Endpoints

### GET /collections/
- **Status:** ⏳ Not yet tested
- **Expected Response:**
  ```json
  [
    {
      "id": "uuid",
      "name": "string",
      "description": "string",
      "active": true,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
  ```

### POST /collections/
- **Status:** ⏳ Not yet tested
- **Expected Request:**
  ```json
  {
    "name": "string (max 50)",
    "description": "string (max 200)",
    "active": true
  }
  ```

### DELETE /collections/{id}
- **Status:** ⏳ Not yet tested
- **Expected:** 204 No Content or success message

## Users Endpoints

### GET /users/me/accessible-files
- **Status:** ⏳ Not yet tested
- **Expected Response:**
  ```json
  [
    {
      "id": "uuid",
      "name": "string",
      "collection_name": "string",
      "size": 0,
      "uploaded_at": "2025-01-01T00:00:00Z"
    }
  ]
  ```

### POST /users/
- **Status:** ⏳ Not yet tested
- **Expected Request:**
  ```json
  {
    "username": "string",
    "password": "string",
    "role": "admin|useradmin|user",
    "collection_id": "uuid"
  }
  ```

## Files Endpoints

### GET /files/list?collection_id={id}
- **Status:** ⏳ Not yet tested
- **Expected Response:**
  ```json
  [
    {
      "id": "uuid",
      "name": "string",
      "size": 0,
      "uploaded_at": "2025-01-01T00:00:00Z",
      "collection_id": "uuid"
    }
  ]
  ```

### POST /files/upload
- **Status:** ⏳ Not yet tested
- **Expected:** multipart/form-data with file and collection_id

### DELETE /files/{id}
- **Status:** ⏳ Not yet tested

### GET /files/download/{id}
- **Status:** ⏳ Not yet tested

## Prompts Endpoints

### GET /prompts/?collection_id={id}
- **Status:** ⏳ Not yet tested

### POST /prompts/
- **Status:** ⏳ Not yet tested

### PUT /prompts/{id}
- **Status:** ⏳ Not yet tested

### DELETE /prompts/{id}
- **Status:** ⏳ Not yet tested

## Chat Endpoints

### POST /chat/ask
- **Status:** ⏳ Not yet tested
- **Expected Request:**
  ```json
  {
    "message": "string",
    "collection_id": "uuid",
    "session_id": "uuid (optional)"
  }
  ```
- **Expected Response:**
  ```json
  {
    "response": "string",
    "session_id": "uuid"
  }
  ```
- **Note:** Streaming support via chunked transfer encoding to be verified

## Activity Endpoints

### GET /activity/recent?limit=50
- **Status:** ⏳ Not yet tested

### GET /activity/stats
- **Status:** ⏳ Not yet tested

## System Health Endpoints

### GET /health
- **Status:** ⏳ Not yet tested

### GET /system/stats/overview
- **Status:** ⏳ Not yet tested

### GET /system/health/detailed
- **Status:** ⏳ Not yet tested

## Next Steps

1. ✅ Frontend implementation complete with mock data support
2. ⏳ Connect to actual backend API
3. ⏳ Test each endpoint and record actual responses
4. ⏳ Update frontend models to match real API responses
5. ⏳ Document any mismatches and required adjustments
6. ⏳ Implement error handling for edge cases discovered during testing

## Error Handling Assumptions

The frontend assumes the following error response format:
```json
{
  "detail": "Error message string"
}
```

If the actual backend uses a different format, the error handling in `AuthContext.tsx` and other service files will need to be updated.

---

*Last Updated: 2025-01-02*
*Status: Initial implementation - awaiting backend integration*
