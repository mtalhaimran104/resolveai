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
    def getTicketTextById(ticket_id):
        ticket = AIServiceHelper.getTicketDetailsById(ticket_id)

        if ticket is None:
            return None

        return (
            f"{ticket['subject']}\n\n"
            f"{ticket['description']}"
        ).strip()
