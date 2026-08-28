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
