from sqlalchemy import text
from app.core.database import engine


class AIServiceHelper:

    @staticmethod
    def prepareResponse(
        data,
        status=True,
        message="Success",
    ):
        return {
            "status": status,
            "message": message,
            "data": data,
        }

    @staticmethod
    def getTicketDetailsById(ticket_id):
        ticket_query = text(
            """
            SELECT id, subject, description
            FROM tickets
            WHERE id = :ticket_id
            """
        )

        with engine.connect() as connection:
            ticket = connection.execute(
                ticket_query,
                {"ticket_id": ticket_id},
            ).mappings().first()

        return ticket

    @staticmethod
    def getKnowledgeBaseArticles():
        """
        Return published Knowledge Base articles enabled
        for AI FAQ retrieval.
        """
        knowledge_query = text(
            """
            SELECT
                id,
                title,
                slug,
                content,
                excerpt,
                category_id,
                status,
                is_public,
                include_in_ai_knowledge_base
            FROM knowledge_articles
            WHERE status = 'PUBLISHED'
              AND is_public = 1
              AND include_in_ai_knowledge_base = 1
            ORDER BY updated_at DESC
            """
        )

        with engine.connect() as connection:
            return connection.execute(
                knowledge_query
            ).mappings().all()

    @staticmethod
    def getTicketTextById(ticket_id):
        ticket = AIServiceHelper.getTicketDetailsById(ticket_id)

        if ticket is None:
            return None

        return (
            f"{ticket['subject']}\n\n"
            f"{ticket['description']}"
        ).strip()

    @staticmethod
    def getArticleFAQ(title, content):
        """
        Send a Knowledge Base article to the AI service
        and return the FAQ response.
        """
        import requests

        response = requests.post(
            "http://ai_service:8000/article-faq/",
            json={
                "title": title,
                "content": content,
            },
            timeout=60,
        )

        response.raise_for_status()
        return response.json()