class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str

class NewSessionRequest(BaseModel):
    title: str = "New Chat"
