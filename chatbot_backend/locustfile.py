from locust import HttpUser, task, between


class ChatUser(HttpUser):
    """
    Simple load-test user that hits the authenticated chat endpoint.

    NOTE:
    - The /ask endpoint in routes_chat.py requires authentication via get_current_user.
    - For this tiny test, we assume your app accepts an Authorization header with a Bearer token.
    - If your auth works differently, adjust the headers in the chat task accordingly.
    """

    # Each simulated user waits 1–3 seconds between chat requests
    wait_time = between(1, 3)

    def on_start(self):
        """
        Called when a simulated user starts. Set up any headers here.

        TODO: Replace the token below if it expires or you switch users.
        """
        # Superadmin JWT obtained from /rag/auth/token
        placeholder_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdXBlcmFkbWluIiwicm9sZSI6InN1cGVyX2FkbWluIiwidXNlcl9pZCI6ImIyZDAxODYxLWFhYjctNGFlNC05OTExLWI1ZjY1YjRkOGZhNSIsIndlYnNpdGVfaWQiOm51bGwsImV4cCI6MTc3MDI5NTA5M30.xsrG40ByjxsVV544-ODJZmXyJY8QaaMy9f0i8ZkmeEI"

        self.headers = {
            # Comment this line out if your local dev server doesn't require auth
            "Authorization": f"Bearer {placeholder_token}",
            "Content-Type": "application/json",
        }

        # Optionally set a fixed collection_id if your user is bound to one
        self.collection_id = None  # e.g. "123e4567-e89b-12d3-a456-426614174000"

    @task
    def chat(self):
        """
        Hit the main authenticated chat endpoint defined in routes_chat.py:

        @router.post("/ask", response_model=ChatResponse, ...)
        async def ask_question(request: ChatRequest, current_user: dict = Depends(get_current_user), ...)

        ChatRequest schema:
            question: str
            top_k: int = 12
            session_id: Optional[str]
            conversation_history: list[ConversationMessage]
            maintain_context: bool
            collection_id: Optional[str]
        """
        payload = {
            "question": "Test question for load testing",
            "top_k": 8,
            "session_id": None,
            "conversation_history": [],
            "maintain_context": False,
            # Set this if your user must specify a collection explicitly; otherwise omit
            "collection_id": self.collection_id,
        }

        with self.client.post(
            "/rag/chat/ask",  # Full path as mounted in app.main
            json=payload,
            headers=self.headers,
            timeout=60,
            name="/rag/chat/ask",
        ) as response:
            # Optionally assert basic success; errors will show in Locust stats
            if response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")

