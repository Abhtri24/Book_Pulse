from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.dependencies import get_session, get_current_author
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_metadata import SnippetMetadata

router = APIRouter(tags=["dashboard"])

@router.get("/api/dev/books", response_model=list[dict[str, Any]])
async def dev_list_books(
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    result = await db.execute(select(Book).where(Book.author_id == author.id))
    books = result.scalars().all()
    return [{"id": str(b.id), "title": b.title, "description": b.description, "status": b.status} for b in books]

@router.get("/api/dev/snippets", response_model=list[dict[str, Any]])
async def dev_list_snippets(
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Snippet).where(Snippet.author_id == author.id).order_by(Snippet.created_at.desc())
    )
    snippets = result.scalars().all()
    response = []
    for snippet in snippets:
        meta_query = await db.execute(
            select(SnippetMetadata).where(SnippetMetadata.snippet_id == snippet.id)
        )
        meta = meta_query.scalar_one_or_none()
        
        response.append({
            "id": str(snippet.id),
            "book_id": str(snippet.book_id),
            "content": snippet.content,
            "chapter_number": snippet.chapter_number,
            "processing_status": snippet.processing_status,
            "embedding_id": snippet.embedding_id,
            "created_at": snippet.created_at.isoformat(),
            "metadata": {
                "primary_genre": meta.primary_genre,
                "sub_genres": meta.sub_genres,
                "pov": meta.pov,
                "pacing": meta.pacing,
                "tone": meta.tone,
                "hook_type": meta.hook_type,
                "readability_score": meta.readability_score,
                "classifier_model": meta.classifier_model,
                "hook_score": meta.hook_score,
                "opening_style": meta.opening_style,
                "curiosity_gap": meta.curiosity_gap,
                "conflict_present": meta.conflict_present,
                "dialogue_opening": meta.dialogue_opening,
            } if meta else None
        })
    return response

@router.get("/", response_class=HTMLResponse)
async def get_dashboard() -> str:
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BookPulse Console</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>✨</text></svg>">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');

        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-border: rgba(255, 255, 255, 0.06);
            --card-hover: rgba(255, 255, 255, 0.06);
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.3);
            --secondary: #10b981;
            --accent: #f43f5e;
            --accent-blue: #06b6d4;
            --accent-orange: #f59e0b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 10% 20%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(6, 182, 212, 0.15) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-color);
            min-height: 100vh;
            line-height: 1.5;
            padding-bottom: 80px;
        }

        header {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--card-border);
        }

        .logo-container {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            font-size: 28px;
            background: linear-gradient(135deg, var(--primary), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .api-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            padding: 6px 12px;
            border-radius: 9999px;
            backdrop-filter: blur(8px);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent);
            box-shadow: 0 0 8px var(--accent);
        }

        .status-dot.online {
            background-color: var(--secondary);
            box-shadow: 0 0 8px var(--secondary);
        }

        main {
            max-width: 1400px;
            margin: 32px auto 0;
            padding: 0 24px;
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 32px;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .content-area {
            display: flex;
            flex-direction: column;
            gap: 32px;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(12px);
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.1);
        }

        .card-title {
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-subtitle {
            font-size: 13px;
            color: var(--text-muted);
            margin-top: -16px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-control {
            width: 100%;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 10px 12px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 14px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }

        textarea.form-control {
            resize: vertical;
            min-height: 120px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 11px 16px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
        }

        .btn:hover {
            opacity: 0.9;
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn:disabled {
            background: var(--card-border);
            color: var(--text-muted);
            cursor: not-allowed;
            transform: none;
            opacity: 0.5;
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-color);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-group {
            display: flex;
            gap: 12px;
        }

        .tabs {
            display: flex;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 16px;
        }

        .tab {
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            color: var(--text-muted);
            border-bottom: 2px solid transparent;
            font-weight: 500;
            transition: color 0.2s, border-color 0.2s;
        }

        .tab.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        .auth-status {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
            border-radius: 9999px;
            text-transform: uppercase;
        }

        .badge-primary { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
        .badge-success { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-danger { background: rgba(244, 63, 94, 0.15); color: #f87171; border: 1px solid rgba(244, 63, 94, 0.3); }

        .token-viewer {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
            font-size: 12px;
            word-break: break-all;
            max-height: 80px;
            overflow-y: auto;
            color: var(--accent-blue);
        }

        /* Health check grid */
        .health-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
        }

        .health-item {
            background: rgba(0, 0, 0, 0.15);
            border: 1px solid var(--card-border);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
        }

        .health-name {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }

        .health-val {
            font-size: 14px;
            font-weight: 600;
        }

        /* Word counter styling */
        .word-counter {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .word-counter.invalid {
            color: var(--accent);
        }

        .word-counter.valid {
            color: var(--secondary);
        }

        /* Snippets Queue list */
        .snippet-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .snippet-item {
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 18px;
            cursor: pointer;
            transition: transform 0.2s, border-color 0.2s, background-color 0.2s;
        }

        .snippet-item:hover {
            border-color: rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.03);
            transform: translateY(-2px);
        }

        .snippet-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .snippet-meta-info {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-muted);
        }

        .snippet-body {
            font-size: 14px;
            color: #d1d5db;
            margin-bottom: 12px;
            white-space: pre-wrap;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .snippet-item.expanded .snippet-body {
            display: block;
            overflow: visible;
            -webkit-line-clamp: unset;
        }

        .snippet-expanded-details {
            border-top: 1px solid var(--card-border);
            padding-top: 16px;
            margin-top: 16px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            animation: fadeIn 0.3s ease-out;
        }

        @media (max-width: 768px) {
            .snippet-expanded-details {
                grid-template-columns: 1fr;
            }
        }

        .detail-block {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .detail-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }

        .detail-value {
            font-size: 13px;
            font-family: monospace;
            word-break: break-all;
            background: rgba(0, 0, 0, 0.2);
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }

        .meta-pill-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .meta-pill {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--card-border);
            padding: 8px 12px;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .meta-pill-label {
            font-size: 9px;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        .meta-pill-val {
            font-size: 12px;
            font-weight: 600;
            color: var(--accent-blue);
        }

        .empty-state {
            text-align: center;
            padding: 48px;
            color: var(--text-muted);
            border: 1px dashed var(--card-border);
            border-radius: 12px;
        }

        /* Toast notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            z-index: 9999;
        }

        .toast {
            background: #1f2937;
            border-left: 4px solid var(--primary);
            border-radius: 8px;
            padding: 16px 20px;
            color: var(--text-color);
            font-size: 14px;
            min-width: 300px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: space-between;
            align-items: center;
            animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .toast.success { border-left-color: var(--secondary); }
        .toast.error { border-left-color: var(--accent); }

        .toast-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 16px;
            padding-left: 12px;
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-container">
            <span class="logo-icon">✨</span>
            <h1>BookPulse Console</h1>
            <span class="badge badge-primary">v0.3.5</span>
        </div>
        <div class="api-status">
            <div id="statusDot" class="status-dot"></div>
            <span id="statusText">Connecting...</span>
        </div>
    </header>

    <main>
        <div class="sidebar">
            <!-- Health Card -->
            <div class="card">
                <div class="card-title">System Health</div>
                <div class="health-grid">
                    <div class="health-item">
                        <div class="health-name">Postgres</div>
                        <div class="health-val" id="healthPostgres">--</div>
                    </div>
                    <div class="health-item">
                        <div class="health-name">Redis</div>
                        <div class="health-val" id="healthRedis">--</div>
                    </div>
                    <div class="health-item">
                        <div class="health-name">Qdrant</div>
                        <div class="health-val" id="healthQdrant">--</div>
                    </div>
                </div>
            </div>

            <!-- Authentication Card -->
            <div class="card" id="authCard">
                <div class="card-title" id="authCardTitle">Authenticate</div>
                
                <div class="tabs" id="authTabs">
                    <div class="tab active" onclick="switchAuthTab('login')">Login</div>
                    <div class="tab" onclick="switchAuthTab('register-author')">Register Author</div>
                    <div class="tab" onclick="switchAuthTab('register-reader')">Register Reader</div>
                </div>

                <!-- Forms -->
                <form id="loginForm" onsubmit="handleLogin(event)">
                    <div class="form-group">
                        <label>Email AddressLabel</label>
                        <input type="email" id="loginEmail" class="form-control" placeholder="author@example.com" required>
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="loginPassword" class="form-control" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn" id="loginBtn">Log In</button>
                </form>

                <form id="registerAuthorForm" onsubmit="handleRegister(event, 'author')" style="display: none;">
                    <div class="form-group">
                        <label>Username</label>
                        <input type="text" id="regAuthorUsername" class="form-control" placeholder="superauthor" required minlength="3">
                    </div>
                    <div class="form-group">
                        <label>Email Address</label>
                        <input type="email" id="regAuthorEmail" class="form-control" placeholder="author@example.com" required>
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="regAuthorPassword" class="form-control" placeholder="••••••••" required minlength="8">
                    </div>
                    <div class="form-group">
                        <label>Bio (Optional)</label>
                        <input type="text" id="regAuthorBio" class="form-control" placeholder="I write epic sci-fi.">
                    </div>
                    <button type="submit" class="btn" id="regAuthorBtn">Register as Author</button>
                </form>

                <form id="registerReaderForm" onsubmit="handleRegister(event, 'reader')" style="display: none;">
                    <div class="form-group">
                        <label>Username</label>
                        <input type="text" id="regReaderUsername" class="form-control" placeholder="avidreader" required minlength="3">
                    </div>
                    <div class="form-group">
                        <label>Email Address</label>
                        <input type="email" id="regReaderEmail" class="form-control" placeholder="reader@example.com" required>
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="regReaderPassword" class="form-control" placeholder="••••••••" required minlength="8">
                    </div>
                    <button type="submit" class="btn" id="regReaderBtn">Register as Reader</button>
                </form>

                <!-- Authenticated State -->
                <div id="authActiveState" class="auth-status" style="display: none;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="badge badge-success" id="roleBadge">Author</span>
                        <button class="btn btn-secondary" style="width: auto; padding: 4px 10px; font-size:12px;" onclick="handleLogout()">Logout</button>
                    </div>
                    <div class="form-group">
                        <label>Bearer Token</label>
                        <div class="token-viewer" id="tokenViewer">--</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="content-area">
            <!-- Author panel (Hidden if not logged in or not Author) -->
            <div id="authorArea" style="display: none; flex-direction: column; gap: 32px;">
                <!-- Create Book -->
                <div class="card">
                    <div class="card-title">Create New Book</div>
                    <form onsubmit="handleCreateBook(event)">
                        <div style="display: grid; grid-template-columns: 1fr 150px; gap: 16px;">
                            <div class="form-group">
                                <label>Book Title</label>
                                <input type="text" id="bookTitle" class="form-control" placeholder="The Starfarer Chronicles" required>
                            </div>
                            <div class="form-group">
                                <label>Status</label>
                                <select id="bookStatus" class="form-control">
                                    <option value="draft">Draft</option>
                                    <option value="published">Published</option>
                                    <option value="completed">Completed</option>
                                    <option value="hiatus">Hiatus</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Description (Optional)</label>
                            <input type="text" id="bookDesc" class="form-control" placeholder="An epic journey across the cosmos.">
                        </div>
                        <button type="submit" class="btn" id="createBookBtn" style="width: auto;">Create Book</button>
                    </form>
                </div>

                <!-- Upload Snippet -->
                <div class="card">
                    <div class="card-title">Upload Fiction Snippet</div>
                    <div class="card-subtitle">Requirements: 200 to 600 words. Celery background pipeline will automatically run embedding, classification, and vector indexing.</div>
                    <form onsubmit="handleUploadSnippet(event)">
                        <div style="display: grid; grid-template-columns: 1fr 150px; gap: 16px;">
                            <div class="form-group">
                                <label>Select Book</label>
                                <select id="snippetBookSelect" class="form-control" required>
                                    <option value="">-- Choose a Book --</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Chapter NumberLabel</label>
                                <input type="number" id="snippetChapter" class="form-control" value="1" min="1" required>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Snippet Content (200-600 words)</label>
                            <textarea id="snippetContent" class="form-control" placeholder="Once upon a time..." required oninput="checkWordCount()"></textarea>
                            <div id="wordCountIndicator" class="word-counter invalid">
                                <span id="wordCountLabel">0 words</span>
                                <span>Range: 200 - 600</span>
                            </div>
                        </div>
                        <button type="submit" class="btn" id="uploadSnippetBtn" disabled style="width: auto;">Upload & Process Snippet</button>
                    </form>
                </div>
            </div>

            <!-- Snippets queue (Visible for authenticated authors) -->
            <div id="snippetsQueueArea" style="display: none;" class="card">
                <div class="card-title">
                    <span>Processed Snippets & Classifier Console</span>
                    <button class="btn btn-secondary" style="width: auto; padding: 4px 12px; font-size:12px; height: 30px;" onclick="loadSnippets()">Refresh</button>
                </div>
                <div id="snippetsList" class="snippet-list">
                    <div class="empty-state">No snippets uploaded yet. Build a book and upload a snippet to view the async pipeline logs.</div>
                </div>
            </div>

            <!-- Standard state for non-authenticated -->
            <div id="anonymousSplash" class="card" style="text-align: center; padding: 60px 24px;">
                <h2 style="font-family:'Outfit', sans-serif; font-size: 24px; margin-bottom: 12px;">Welcome to BookPulse</h2>
                <p style="color: var(--text-muted); max-width: 500px; margin: 0 auto 24px;">
                    BookPulse uses state-of-the-art embedding pipelines and structured LLM classifiers to build candidate vector indexes. Log in as an Author to start publishing and running the pipeline.
                </p>
                <div style="display: flex; gap: 12px; justify-content: center;">
                    <button class="btn" style="width: auto;" onclick="focusLogin()">Get Started</button>
                </div>
            </div>
        </div>
    </main>

    <div class="toast-container" id="toastContainer"></div>

    <script>
        const API_URL = "";
        let activeToken = localStorage.getItem("token") || "";
        let activeRole = localStorage.getItem("role") || "";
        let books = [];
        let pollingInterval = null;

        // On Load
        window.addEventListener("load", () => {
            checkAPIHealth();
            setInterval(checkAPIHealth, 10000);
            
            if (activeToken) {
                renderAuthenticatedState();
            } else {
                renderAnonymousState();
            }
        });

        function showToast(message, type = "info") {
            const container = document.getElementById("toastContainer");
            const toast = document.createElement("div");
            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <span>${message}</span>
                <button class="toast-close" onclick="this.parentElement.remove()">×</button>
            `;
            container.appendChild(toast);
            setTimeout(() => {
                toast.remove();
            }, 4000);
        }

        async function checkAPIHealth() {
            try {
                const res = await fetch(`${API_URL}/health`);
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById("statusDot").className = "status-dot online";
                    document.getElementById("statusText").innerText = "API Online";
                    
                    document.getElementById("healthPostgres").innerHTML = data.postgres === "ok" ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-danger">FAIL</span>';
                    document.getElementById("healthRedis").innerHTML = data.redis === "ok" ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-danger">FAIL</span>';
                    document.getElementById("healthQdrant").innerHTML = data.qdrant === "ok" ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-danger">FAIL</span>';
                } else {
                    setOfflineState();
                }
            } catch (err) {
                setOfflineState();
            }
        }

        function setOfflineState() {
            document.getElementById("statusDot").className = "status-dot";
            document.getElementById("statusText").innerText = "API Offline";
            document.getElementById("healthPostgres").innerHTML = '<span class="badge badge-danger">--</span>';
            document.getElementById("healthRedis").innerHTML = '<span class="badge badge-danger">--</span>';
            document.getElementById("healthQdrant").innerHTML = '<span class="badge badge-danger">--</span>';
        }

        function switchAuthTab(tab) {
            const tabs = document.querySelectorAll("#authTabs .tab");
            tabs.forEach(t => t.classList.remove("active"));
            
            document.getElementById("loginForm").style.display = "none";
            document.getElementById("registerAuthorForm").style.display = "none";
            document.getElementById("registerReaderForm").style.display = "none";

            if (tab === "login") {
                tabs[0].classList.add("active");
                document.getElementById("loginForm").style.display = "block";
            } else if (tab === "register-author") {
                tabs[1].classList.add("active");
                document.getElementById("registerAuthorForm").style.display = "block";
            } else if (tab === "register-reader") {
                tabs[2].classList.add("active");
                document.getElementById("registerReaderForm").style.display = "block";
            }
        }

        function focusLogin() {
            document.getElementById("authCard").scrollIntoView({ behavior: 'smooth' });
            switchAuthTab('login');
        }

        async function handleLogin(e) {
            e.preventDefault();
            const email = document.getElementById("loginEmail").value;
            const password = document.getElementById("loginPassword").value;
            const btn = document.getElementById("loginBtn");

            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span>Logging in...`;

            try {
                const res = await fetch(`${API_URL}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    json: true,
                    body: JSON.stringify({ email, password })
                });

                if (res.ok) {
                    const data = await res.json();
                    activeToken = data.access_token;
                    
                    // Simple JWT payload parser to extract role
                    try {
                        const payload = JSON.parse(atob(activeToken.split('.')[1]));
                        activeRole = payload.type || "author";
                    } catch (e) {
                        activeRole = "author";
                    }

                    localStorage.setItem("token", activeToken);
                    localStorage.setItem("role", activeRole);
                    
                    showToast("Successfully authenticated!", "success");
                    renderAuthenticatedState();
                } else {
                    const err = await res.json();
                    showToast(err.detail || "Authentication failed", "error");
                }
            } catch (err) {
                showToast("Connection error occurred", "error");
            } finally {
                btn.disabled = false;
                btn.innerText = "Log In";
            }
        }

        async function handleRegister(e, role) {
            e.preventDefault();
            const isAuthor = role === "author";
            const username = document.getElementById(isAuthor ? "regAuthorUsername" : "regReaderUsername").value;
            const email = document.getElementById(isAuthor ? "regAuthorEmail" : "regReaderEmail").value;
            const password = document.getElementById(isAuthor ? "regAuthorPassword" : "regReaderPassword").value;
            const bio = isAuthor ? document.getElementById("regAuthorBio").value : "";
            const btn = document.getElementById(isAuthor ? "regAuthorBtn" : "regReaderBtn");

            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span>Registering...`;

            try {
                const endpoint = isAuthor ? "/auth/register/author" : "/auth/register/reader";
                const payload = { username, email, password };
                if (isAuthor) payload.bio = bio;

                const res = await fetch(`${API_URL}${endpoint}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    showToast("Account created successfully! Please login.", "success");
                    switchAuthTab("login");
                    document.getElementById("loginEmail").value = email;
                    document.getElementById("loginPassword").value = password;
                } else {
                    const err = await res.json();
                    showToast(err.detail || "Registration failed", "error");
                }
            } catch (err) {
                showToast("Connection error occurred", "error");
            } finally {
                btn.disabled = false;
                btn.innerText = isAuthor ? "Register as Author" : "Register as Reader";
            }
        }

        function handleLogout() {
            activeToken = "";
            activeRole = "";
            localStorage.removeItem("token");
            localStorage.removeItem("role");
            showToast("Logged out successfully");
            renderAnonymousState();
            
            if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        }

        function renderAuthenticatedState() {
            document.getElementById("authTabs").style.display = "none";
            document.getElementById("loginForm").style.display = "none";
            document.getElementById("registerAuthorForm").style.display = "none";
            document.getElementById("registerReaderForm").style.display = "none";
            
            document.getElementById("authCardTitle").innerText = "Session Active";
            document.getElementById("authActiveState").style.display = "flex";
            document.getElementById("roleBadge").innerText = activeRole === "author" ? "Author Mode" : "Reader Mode";
            document.getElementById("roleBadge").className = `badge ${activeRole === "author" ? 'badge-primary' : 'badge-success'}`;
            document.getElementById("tokenViewer").innerText = activeToken;

            document.getElementById("anonymousSplash").style.display = "none";

            if (activeRole === "author") {
                document.getElementById("authorArea").style.display = "flex";
                document.getElementById("snippetsQueueArea").style.display = "block";
                loadBooks();
                loadSnippets();
                
                if (!pollingInterval) {
                    pollingInterval = setInterval(loadSnippets, 5000);
                }
            } else {
                document.getElementById("authorArea").style.display = "none";
                document.getElementById("snippetsQueueArea").style.display = "none";
                document.getElementById("anonymousSplash").style.display = "block";
                document.getElementById("anonymousSplash").querySelector("h2").innerText = "Logged in as Reader";
                document.getElementById("anonymousSplash").querySelector("p").innerText = "Reader recommendation feeds and engagement models are currently in active development. Stay tuned for Phase 5!";
                document.getElementById("anonymousSplash").querySelector("button").style.display = "none";
            }
        }

        function renderAnonymousState() {
            document.getElementById("authTabs").style.display = "flex";
            document.getElementById("authActiveState").style.display = "none";
            document.getElementById("authCardTitle").innerText = "Authenticate";
            switchAuthTab("login");

            document.getElementById("authorArea").style.display = "none";
            document.getElementById("snippetsQueueArea").style.display = "none";
            document.getElementById("anonymousSplash").style.display = "block";
            document.getElementById("anonymousSplash").querySelector("h2").innerText = "Welcome to BookPulse";
            document.getElementById("anonymousSplash").querySelector("p").innerText = "BookPulse uses state-of-the-art embedding pipelines and structured LLM classifiers to build candidate vector indexes. Log in as an Author to start publishing and running the pipeline.";
            document.getElementById("anonymousSplash").querySelector("button").style.display = "inline-flex";
        }

        async function loadBooks() {
            try {
                const res = await fetch(`${API_URL}/api/dev/books`, {
                    headers: { "Authorization": `Bearer ${activeToken}` }
                });
                if (res.ok) {
                    books = await res.json();
                    const select = document.getElementById("snippetBookSelect");
                    
                    // Preserve selected value if still valid
                    const currentVal = select.value;
                    select.innerHTML = '<option value="">-- Choose a Book --</option>';
                    
                    books.forEach(b => {
                        const opt = document.createElement("option");
                        opt.value = b.id;
                        opt.innerText = `${b.title} [${b.status}]`;
                        select.appendChild(opt);
                    });

                    if (currentVal && books.some(b => b.id === currentVal)) {
                        select.value = currentVal;
                    }
                }
            } catch (err) {
                console.error("Error loading books", err);
            }
        }

        async function handleCreateBook(e) {
            e.preventDefault();
            const title = document.getElementById("bookTitle").value;
            const status = document.getElementById("bookStatus").value;
            const description = document.getElementById("bookDesc").value;
            const btn = document.getElementById("createBookBtn");

            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span>Creating...`;

            try {
                const res = await fetch(`${API_URL}/books`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${activeToken}`
                    },
                    body: JSON.stringify({ title, status, description })
                });

                if (res.ok) {
                    showToast("Book created successfully!", "success");
                    document.getElementById("bookTitle").value = "";
                    document.getElementById("bookDesc").value = "";
                    await loadBooks();
                } else {
                    const err = await res.json();
                    showToast(err.detail || "Failed to create book", "error");
                }
            } catch (err) {
                showToast("Connection error", "error");
            } finally {
                btn.disabled = false;
                btn.innerText = "Create Book";
            }
        }

        function checkWordCount() {
            const text = document.getElementById("snippetContent").value;
            const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
            const label = document.getElementById("wordCountLabel");
            const indicator = document.getElementById("wordCountIndicator");
            const uploadBtn = document.getElementById("uploadSnippetBtn");

            label.innerText = `${wordCount} word${wordCount === 1 ? '' : 's'}`;

            if (wordCount >= 200 && wordCount <= 600) {
                indicator.className = "word-counter valid";
                uploadBtn.disabled = false;
            } else {
                indicator.className = "word-counter invalid";
                uploadBtn.disabled = true;
            }
        }

        async function handleUploadSnippet(e) {
            e.preventDefault();
            const bookId = document.getElementById("snippetBookSelect").value;
            const chapterNumber = parseInt(document.getElementById("snippetChapter").value);
            const content = document.getElementById("snippetContent").value;
            const btn = document.getElementById("uploadSnippetBtn");

            if (!bookId) {
                showToast("Please select a book", "error");
                return;
            }

            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span>Uploading...`;

            try {
                const res = await fetch(`${API_URL}/books/${bookId}/snippets`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${activeToken}`
                    },
                    body: JSON.stringify({ content, chapter_number: chapterNumber })
                });

                if (res.ok) {
                    showToast("Snippet uploaded and background process enqueued!", "success");
                    document.getElementById("snippetContent").value = "";
                    document.getElementById("snippetChapter").value = chapterNumber + 1;
                    checkWordCount();
                    await loadSnippets();
                } else {
                    const err = await res.json();
                    showToast(err.detail || "Upload failed", "error");
                }
            } catch (err) {
                showToast("Connection error", "error");
            } finally {
                btn.disabled = false;
                btn.innerText = "Upload & Process Snippet";
            }
        }

        async function loadSnippets() {
            if (!activeToken || activeRole !== "author") return;
            try {
                const res = await fetch(`${API_URL}/api/dev/snippets`, {
                    headers: { "Authorization": `Bearer ${activeToken}` }
                });
                if (res.ok) {
                    const snippets = await res.json();
                    renderSnippetsList(snippets);
                }
            } catch (err) {
                console.error("Error loading snippets", err);
            }
        }

        function renderSnippetsList(snippets) {
            const list = document.getElementById("snippetsList");
            if (snippets.length === 0) {
                list.innerHTML = `<div class="empty-state">No snippets uploaded yet. Build a book and upload a snippet to view the async pipeline logs.</div>`;
                return;
            }

            // Keep track of which snippets are currently expanded
            const expandedSnippetIds = new Set();
            document.querySelectorAll(".snippet-item.expanded").forEach(item => {
                expandedSnippetIds.add(item.dataset.id);
            });

            list.innerHTML = "";
            snippets.forEach(snippet => {
                const isExpanded = expandedSnippetIds.has(snippet.id);
                const book = books.find(b => b.id === snippet.book_id);
                const bookTitle = book ? book.title : "Unknown Book";
                
                const item = document.createElement("div");
                item.className = `snippet-item ${isExpanded ? 'expanded' : ''}`;
                item.dataset.id = snippet.id;
                
                let badgeClass = "badge-primary";
                if (snippet.processing_status === "ready") badgeClass = "badge-success";
                if (snippet.processing_status === "processing") badgeClass = "badge-warning";
                if (snippet.processing_status === "failed") badgeClass = "badge-danger";

                item.innerHTML = `
                    <div class="snippet-header">
                        <div class="snippet-meta-info">
                            <strong style="color: var(--text-color);">${bookTitle}</strong>
                            <span>•</span>
                            <span>Chapter ${snippet.chapter_number}</span>
                        </div>
                        <span class="badge ${badgeClass}">${snippet.processing_status}</span>
                    </div>
                    <div class="snippet-body">${snippet.content}</div>
                `;

                if (isExpanded) {
                    appendExpandedDetails(item, snippet);
                }

                item.addEventListener("click", (e) => {
                    // Prevent toggling if clicking inside inputs/buttons
                    if (e.target.closest('.snippet-expanded-details')) return;
                    
                    item.classList.toggle("expanded");
                    if (item.classList.contains("expanded")) {
                        appendExpandedDetails(item, snippet);
                    } else {
                        const details = item.querySelector(".snippet-expanded-details");
                        if (details) details.remove();
                    }
                });

                list.appendChild(item);
            });
        }

        function appendExpandedDetails(item, snippet) {
            // Remove existing details if any
            const existing = item.querySelector(".snippet-expanded-details");
            if (existing) existing.remove();

            const details = document.createElement("div");
            details.className = "snippet-expanded-details";

            let metadataHtml = "";
            if (snippet.metadata) {
                const m = snippet.metadata;
                metadataHtml = `
                    <div class="detail-block" style="grid-column: span 2;">
                        <span class="detail-label">Extracted Classifier Metadata (Groq Llama 3.3)</span>
                        <div class="meta-pill-grid" style="margin-top:8px;">
                            <div class="meta-pill">
                                <span class="meta-pill-label">Primary Genre</span>
                                <span class="meta-pill-val" style="text-transform: capitalize;">${m.primary_genre}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Sub-Genres</span>
                                <span class="meta-pill-val" style="font-size:11px;">${m.sub_genres.join(', ') || 'None'}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Pacing & POV</span>
                                <span class="meta-pill-val" style="text-transform: capitalize; font-size:11px;">${m.pacing} / ${m.pov.replace('_', ' ')}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Readability Score</span>
                                <span class="meta-pill-val">${m.readability_score.toFixed(1)} / 100</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Tone</span>
                                <span class="meta-pill-val" style="text-transform: capitalize; font-size:11px;">${m.tone}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Hook Score</span>
                                <span class="meta-pill-val">${m.hook_score} / 100</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Hook Type</span>
                                <span class="meta-pill-val" style="text-transform: capitalize;">${m.hook_type}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Opening Style</span>
                                <span class="meta-pill-val" style="text-transform: capitalize; font-size:11px;">${m.opening_style.replace(/_/g, ' ')}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Curiosity Gap</span>
                                <span class="meta-pill-val">${m.curiosity_gap ? 'Yes' : 'No'}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Conflict Present</span>
                                <span class="meta-pill-val">${m.conflict_present ? 'Yes' : 'No'}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">Dialogue Opening</span>
                                <span class="meta-pill-val">${m.dialogue_opening ? 'Yes' : 'No'}</span>
                            </div>
                            <div class="meta-pill">
                                <span class="meta-pill-label">LLM Model</span>
                                <span class="meta-pill-val" style="font-size: 10px; color: var(--text-muted);">${m.classifier_model}</span>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                metadataHtml = `
                    <div class="detail-block" style="grid-column: span 2;">
                        <span class="detail-label">Classifier Metadata</span>
                        <div style="font-size:13px; color:var(--text-muted); padding:12px; background: rgba(0,0,0,0.1); border-radius:8px; margin-top:8px; border: 1px dashed var(--card-border);">
                            ${snippet.processing_status === 'failed' ? 'Pipeline processing failed. Check your GROQ_API_KEY environment variable.' : 'Classification is pending processing. Celery worker is compiling results...'}
                        </div>
                    </div>
                `;
            }

            details.innerHTML = `
                <div class="detail-block">
                    <span class="detail-label">Snippet Database UUID</span>
                    <span class="detail-value">${snippet.id}</span>
                </div>
                <div class="detail-block">
                    <span class="detail-label">Qdrant Vector Index ID</span>
                    <span class="detail-value">${snippet.embedding_id || 'Not indexed yet'}</span>
                </div>
                ${metadataHtml}
            `;
            item.appendChild(details);
        }
    </script>
</body>
</html>
"""
