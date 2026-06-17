import pytest
from sqlalchemy import select

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_feedback import SnippetFeedback


@pytest.mark.asyncio
async def test_snippet_feedback_persists_as_one_to_one(db_session):
    author = Author(
        username="feedback-author",
        email="feedback-author@example.com",
        password_hash="hash",
    )
    book = Book(author=author, title="Feedback Story", description="")
    snippet = Snippet(
        author=author,
        book=book,
        content="sample",
        chapter_number=1,
    )
    feedback = SnippetFeedback(
        snippet=snippet,
        strengths=["Strong opening hook", "Vivid imagery"],
        improvements=["Tighten middle pacing", "Clarify protagonist goal"],
        hook_score=8,
        rewrite_suggestion="Try opening with the character's dilemma in the first sentence.",
        agent_model="test-agent",
    )
    db_session.add_all([author, book, snippet, feedback])
    await db_session.commit()

    result = await db_session.execute(select(SnippetFeedback))
    saved_feedback = result.scalar_one()

    assert saved_feedback.snippet_id == snippet.id
    assert saved_feedback.strengths == ["Strong opening hook", "Vivid imagery"]
    assert saved_feedback.improvements == ["Tighten middle pacing", "Clarify protagonist goal"]
    assert saved_feedback.hook_score == 8
    assert saved_feedback.snippet.feedback_record.rewrite_suggestion.startswith("Try opening")
