"""Populate the database with realistic demo tickets.

A fresh setup has roles, departments and categories (seeded by data
migrations) but no tickets, so the dashboard, ticket list and reports pages
all render empty and the AI endpoints have no ticket_id to work with.

With --with-ai the seeder does not invent the AI fields. It calls the running
FastAPI service for every ticket, so category, priority and sentiment are real
model predictions and the ai_analyses table is populated by the service itself
exactly as it would be in production.

Everything created is tagged so it can be removed again: demo users carry the
DEMO_USER_PREFIX and demo tickets are the ones they requested. --flush deletes
that set and nothing else.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, RoleCode, UserRole
from ai.services import (
    AIServiceError,
    call_classification_service,
    call_priority_service,
    call_sentiment_service,
)
from classification.models import TicketCategory
from organization.models import Department
from tickets.models import Ticket, TicketComment, TicketHistory

User = get_user_model()

DEMO_USER_PREFIX = "demo_"
DEMO_PASSWORD = "DemoPass123!"

REQUESTERS = [
    ("demo_ayesha", "ayesha.khan@demo.iub.edu.pk", "Ayesha", "Khan"),
    ("demo_bilal", "bilal.ahmed@demo.iub.edu.pk", "Bilal", "Ahmed"),
    ("demo_fatima", "fatima.noor@demo.iub.edu.pk", "Fatima", "Noor"),
    ("demo_hamza", "hamza.raza@demo.iub.edu.pk", "Hamza", "Raza"),
    ("demo_sana", "sana.iqbal@demo.iub.edu.pk", "Sana", "Iqbal"),
    ("demo_owais", "owais.javed@demo.iub.edu.pk", "Owais", "Javed"),
    ("demo_mariam", "mariam.saeed@demo.iub.edu.pk", "Mariam", "Saeed"),
    ("demo_danish", "danish.qureshi@demo.iub.edu.pk", "Danish", "Qureshi"),
]

AGENTS = [
    ("demo_agent_imran", "imran.agent@demo.iub.edu.pk", "Imran", "Shah", "IT Support"),
    ("demo_agent_zara", "zara.agent@demo.iub.edu.pk", "Zara", "Malik", "Examination"),
    ("demo_agent_usman", "usman.agent@demo.iub.edu.pk", "Usman", "Tariq", "Admissions"),
    ("demo_agent_nida", "nida.agent@demo.iub.edu.pk", "Nida", "Aslam", "Finance"),
]

SUPERVISORS = [
    ("demo_sup_kamran", "kamran.sup@demo.iub.edu.pk", "Kamran", "Latif"),
]

AGENT_REPLIES = [
    "Thank you for reaching out. We have received your request and are looking into it.",
    "We are checking this with the relevant department and will update you shortly.",
    "Could you please confirm your enrolment number so we can locate your record?",
    "This has been escalated to the concerned office. We appreciate your patience.",
]

REQUESTER_FOLLOWUPS = [
    "Thank you, please let me know once there is an update.",
    "Any progress on this? The deadline is approaching.",
    "I have attached the requested details. Kindly proceed.",
]

SENTIMENT_BY_PRIORITY = {
    "CRITICAL": "NEGATIVE",
    "HIGH": "NEGATIVE",
    "MEDIUM": "NEUTRAL",
    "LOW": "NEUTRAL",
}

SENTIMENT_MAP = {
    "positive": "POSITIVE",
    "neutral": "NEUTRAL",
    "negative": "NEGATIVE",
}

PRIORITY_MAP = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "CRITICAL",
}

RESOLVED_STATUSES = {"RESOLVED", "CLOSED"}


def _stamp(instance, model, when):
    """Force an auto_now_add timestamp to a chosen moment."""
    model.objects.filter(pk=instance.pk).update(created_at=when, updated_at=when)
    return instance

# (subject, description, fallback_category, fallback_priority, status)
TICKETS = [
 ("Cannot download my transcript","I have been trying to download my official transcript from the student portal for three days. The download button returns an error page every time. I need it for a scholarship application due next week.","Transcript","HIGH","OPEN"),
 ("Transcript shows wrong CGPA","My issued transcript lists my CGPA as 3.12 but my portal shows 3.42. One of the two is wrong and I need the corrected document urgently.","Transcript","HIGH","IN_PROGRESS"),
 ("Need an additional transcript copy","I already collected one transcript last semester and now require a second attested copy for a visa application. What is the fee and process?","Transcript","LOW","CLOSED"),
 ("Result not showing for BSCS-402","My result for BSCS-402 is still blank on the portal although results for every other course were published last Friday. Please check whether my marks were uploaded.","Result","HIGH","IN_PROGRESS"),
 ("Result withheld without reason","My semester result says withheld but I have no dues pending and my clearance is complete. Nobody has told me why.","Result","CRITICAL","OPEN"),
 ("Recheck request for final paper","I would like to request a rechecking of my Database Systems final paper. The marks awarded do not match my expectation at all.","Result","MEDIUM","WAITING_FOR_USER"),
 ("Fee challan shows wrong amount","The challan generated for this semester shows the full tuition amount and does not account for my approved 50% merit scholarship. I do not want to pay the wrong amount before the deadline.","Fee & Challan","CRITICAL","IN_PROGRESS"),
 ("Duplicate fee payment","I paid my semester fee twice because the first transaction showed as failed but was actually debited. How do I claim a refund?","Fee & Challan","CRITICAL","IN_PROGRESS"),
 ("Challan not generating at all","When I click generate challan the page just reloads and nothing downloads. The due date is in four days and I cannot pay without it.","Fee & Challan","HIGH","OPEN"),
 ("Late fee charged incorrectly","I paid before the deadline but a late fee surcharge has been added to my account. I have the bank receipt with the date on it.","Fee & Challan","HIGH","RESOLVED"),
 ("Locked out of the student portal","After changing my password yesterday I can no longer log in. The portal says my account is locked. I have tried the reset link twice and it never arrives.","Account & Login","HIGH","RESOLVED"),
 ("Password reset email never arrives","I have requested a password reset six times today and no email has arrived, not even in spam. My registered address is correct.","Account & Login","HIGH","OPEN"),
 ("Two factor code not received","The portal now asks for an SMS code but my phone never receives it. I am completely unable to log in.","Account & Login","CRITICAL","IN_PROGRESS"),
 ("Account shows as inactive","My account status reads inactive although I am an enrolled student this semester and have paid my fee.","Account & Login","HIGH","OPEN"),
 ("Unable to register for elective","The registration page says the elective Data Mining is full, but the department office told me seats were added this morning.","Course Registration","MEDIUM","OPEN"),
 ("Cannot drop a course","The drop button is greyed out for one of my courses even though the add and drop period is still open until Friday.","Course Registration","MEDIUM","IN_PROGRESS"),
 ("Prerequisite wrongly enforced","The system refuses to register me for Advanced Algorithms saying I lack the prerequisite, but I passed Data Structures last semester.","Course Registration","HIGH","OPEN"),
 ("Registered course missing from timetable","One of the four courses I registered for does not appear on my timetable, although it appears on my fee challan.","Course Registration","MEDIUM","RESOLVED"),
 ("Scholarship disbursement delayed","My merit scholarship for the spring semester has still not been disbursed. The finance office says it was approved in March.","Scholarship","MEDIUM","WAITING_FOR_USER"),
 ("Scholarship application status unclear","I applied for the need based scholarship two months ago and the portal still shows no status at all.","Scholarship","MEDIUM","OPEN"),
 ("Scholarship revoked without notice","My scholarship has been removed from my account this semester with no email or explanation. My CGPA is above the requirement.","Scholarship","CRITICAL","IN_PROGRESS"),
 ("Degree verification for employer","My employer needs my degree verified directly by the university. What is the process and how long does it usually take?","Certificate / Verification","LOW","RESOLVED"),
 ("Attestation of documents","I need my degree and transcript attested for an overseas application. Which office handles this and what are the timings?","Certificate / Verification","LOW","CLOSED"),
 ("Verification letter has wrong dates","The verification letter issued to me lists my enrolment period incorrectly, showing 2019 instead of 2020.","Certificate / Verification","MEDIUM","OPEN"),
 ("Portal very slow during peak hours","Between 9am and 11am the student portal takes over a minute to load any page. It is usable in the evening.","Portal Technical Issue","MEDIUM","OPEN"),
 ("Portal logs me out every few minutes","The portal signs me out roughly every three minutes, so I lose whatever form I was filling in.","Portal Technical Issue","HIGH","IN_PROGRESS"),
 ("File upload fails on the portal","Every attempt to upload my supporting documents fails at around eighty percent with a generic error.","Portal Technical Issue","HIGH","OPEN"),
 ("Portal not working on mobile","The portal layout is broken on my phone and the submit button is off screen, so I cannot complete registration.","Portal Technical Issue","MEDIUM","RESOLVED"),
 ("Exam date clash for two courses","Two of my registered courses have their final exams scheduled at the same time on the 14th. Please advise how this is resolved.","Examination","HIGH","IN_PROGRESS"),
 ("Exam roll number slip not issued","My roll number slip has not been generated and the exams begin on Monday. Other students in my section received theirs.","Examination","CRITICAL","OPEN"),
 ("Request for special exam","I was hospitalised during the midterm week and have medical documentation. Can a special exam be arranged?","Examination","HIGH","WAITING_FOR_USER"),
 ("Exam centre location incorrect","My roll number slip lists a campus I have never attended. I am enrolled at the main campus.","Examination","HIGH","OPEN"),
 ("Misspelled name on student card","My name is printed as Muhamad on my student card instead of Muhammad. I need this corrected before my transcript is issued.","Name Correction","LOW","OPEN"),
 ("Father name incorrect in records","My father's name is spelled incorrectly in all university records and does not match my national identity card.","Name Correction","MEDIUM","IN_PROGRESS"),
 ("Date of birth wrong on portal","My date of birth is recorded as 1999 instead of 2000, which does not match my documents.","Name Correction","MEDIUM","OPEN"),
 ("Admission status still pending","I submitted my admission application four weeks ago and the status has not changed from Under Review. The prospectus said two weeks.","Admission","MEDIUM","WAITING_FOR_USER"),
 ("Merit list not published","The merit list for the BS Computer Science programme was due last week and has still not appeared anywhere.","Admission","HIGH","OPEN"),
 ("Admission documents rejected","My submitted documents were marked as rejected with no reason given. I believe everything required was attached.","Admission","HIGH","IN_PROGRESS"),
 ("Library clearance not reflected","I returned all my library books last month and have the receipt, but my clearance form still shows an outstanding item.","Clearance","MEDIUM","RESOLVED"),
 ("Hostel clearance pending","My hostel clearance has been pending for three weeks. I have vacated the room and returned the key.","Clearance","MEDIUM","OPEN"),
 ("Clearance form not downloadable","The clearance form download link returns a blank page. I need the signed form to collect my degree.","Clearance","MEDIUM","IN_PROGRESS"),
 ("Thesis supervisor not assigned","The deadline for the thesis proposal is in two weeks and I still have not been assigned a supervisor.","Thesis","HIGH","OPEN"),
 ("Thesis submission portal closed early","The submission portal closed a day earlier than the announced deadline and I could not upload my thesis.","Thesis","CRITICAL","IN_PROGRESS"),
 ("Change of thesis topic request","I would like to request a change of thesis topic after discussion with my supervisor. What is the procedure?","Thesis","LOW","WAITING_FOR_USER"),
 ("Update my registered mobile number","I changed my phone number and the portal will not let me edit it. All the OTP messages still go to my old number.","Profile Update","LOW","CLOSED"),
 ("Cannot change my profile photo","The profile photo upload keeps failing and my card still shows an outdated picture.","Profile Update","LOW","OPEN"),
 ("Update permanent address","I have moved and need my permanent address updated in the university records for postal correspondence.","Profile Update","LOW","RESOLVED"),
 ("Degree collection procedure","I graduated in the last convocation. What is the procedure and timeline for collecting my original degree?","Degree","LOW","CLOSED"),
 ("Degree not issued after two years","I completed my programme two years ago and my original degree has still not been issued despite several visits.","Degree","HIGH","OPEN"),
 ("Air conditioning not working in Lab 3","The air conditioning in Computer Lab 3 has been out for a week. It is difficult to sit through afternoon sessions.","Infrastructure / Maintenance","MEDIUM","IN_PROGRESS"),
 ("Broken chairs in lecture hall B","Several chairs in lecture hall B are broken and there is not enough seating for the whole section.","Infrastructure / Maintenance","LOW","OPEN"),
 ("No drinking water in the department","The water cooler on the second floor has been out of order for over two weeks.","Infrastructure / Maintenance","MEDIUM","RESOLVED"),
 ("Wifi not reachable in the library","The campus wifi has no signal on the library's upper floor, which makes research work impossible there.","Infrastructure / Maintenance","MEDIUM","OPEN"),
 ("No response from department office","I have emailed the department office three times over two weeks about my course withdrawal and received no reply at all.","Complaint","HIGH","OPEN"),
 ("Rude behaviour at the help desk","I was spoken to very rudely at the administration help desk when asking about my challan. This is unacceptable.","Complaint","HIGH","IN_PROGRESS"),
 ("Repeated delays in every request","Every single request I have submitted this year has taken more than a month. This is extremely frustrating.","Complaint","CRITICAL","OPEN"),
 ("Salary slip not generated","My salary slip for last month has not been generated in the employee portal, although the salary was credited.","Employee Services","MEDIUM","RESOLVED"),
 ("Leave balance showing incorrectly","My annual leave balance shows four days but I have only used six of my thirty day entitlement.","Employee Services","MEDIUM","OPEN"),
 ("Request for bonafide certificate","I need a bonafide certificate for a visa application. Where do I apply and what documents are required?","Other","LOW","CLOSED"),
 ("Lost my student identity card","I lost my student card on campus yesterday. What is the procedure for a replacement and is there a fee?","Other","LOW","OPEN"),
]

class Command(BaseCommand):
    help = "Create demo users, tickets, comments and history so the UI has data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete previously seeded demo data instead of creating it.",
        )
        parser.add_argument(
            "--with-ai",
            action="store_true",
            help=(
                "Call the running AI service for every ticket so category, "
                "priority and sentiment are real predictions and ai_analyses "
                "is populated. Requires ai_service to be up."
            ),
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed, so repeated runs produce the same data.",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()
            return

        random.seed(options["seed"])

        with transaction.atomic():
            requesters = self._create_users(REQUESTERS, RoleCode.REQUESTER)
            supervisors = self._create_users(SUPERVISORS, RoleCode.SUPERVISOR)
            agents = self._create_agents()
            tickets = self._create_tickets(requesters, agents)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(requesters)} requesters, {len(agents)} agents, "
            f"{len(supervisors)} supervisor(s) and {len(tickets)} tickets."
        ))

        if options["with_ai"]:
            self._apply_ai(tickets)

        self.stdout.write(f"Demo accounts use the password: {DEMO_PASSWORD}")
        self.stdout.write(
            "Remove it all again with: manage.py seed_demo_data --flush"
        )

    # -- creation ---------------------------------------------------------

    def _create_users(self, specs, role_code):
        role = Role.objects.filter(code=role_code).first()
        users = []

        for username, email, first, last in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            if role is not None:
                UserRole.objects.get_or_create(user=user, role=role)
            users.append(user)

        return users

    def _create_agents(self):
        role = Role.objects.filter(code=RoleCode.AGENT).first()
        agents = []

        for username, email, first, last, dept_name in AGENTS:
            department = Department.objects.filter(name=dept_name).first()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "is_active": True,
                    "is_verified": True,
                    "is_staff": True,
                    "department": department,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            if role is not None:
                UserRole.objects.get_or_create(user=user, role=role)
            agents.append(user)

        return agents

    def _create_tickets(self, requesters, agents):
        now = timezone.now()
        created = []

        for index, row in enumerate(TICKETS):
            subject, body, cat_name, priority, status = row

            existing = Ticket.objects.filter(subject=subject).first()
            if existing is not None:
                created.append(existing)
                continue

            category = TicketCategory.objects.filter(name=cat_name).first()
            requester = requesters[index % len(requesters)]
            assigned = None if status == "OPEN" else agents[index % len(agents)]

            ticket = Ticket.objects.create(
                subject=subject,
                description=body,
                requester=requester,
                assigned_to=assigned,
                category=category,
                department=category.department if category else None,
                priority=priority,
                status=status,
                sentiment=SENTIMENT_BY_PRIORITY[priority],
                ai_confidence=round(random.uniform(78.0, 97.0), 2),
            )

            # Spread creation over the last 60 days so the reports pages have a
            # time series to plot rather than a single spike at setup time.
            #
            # Every related row is dated inside the ticket's own lifetime.
            # Timestamps are auto_now/auto_now_add, so they have to be forced
            # with update() after the fact -- otherwise a ticket opened 60
            # days ago carries a reply written "now", and the resolution-time
            # report honestly reports a first response of several weeks.
            age_days = random.randint(0, 60)
            opened = now - timedelta(days=age_days, hours=random.randint(0, 23))

            first_reply_at = opened + timedelta(
                minutes=random.randint(15, 600)
            )
            resolved_at = first_reply_at + timedelta(
                hours=random.randint(1, 72)
            )
            if resolved_at > now:
                resolved_at = now

            is_resolved = status in RESOLVED_STATUSES

            Ticket.objects.filter(pk=ticket.pk).update(
                created_at=opened,
                updated_at=resolved_at if is_resolved else first_reply_at,
                resolved_at=resolved_at if is_resolved else None,
            )

            _stamp(
                TicketHistory.objects.create(
                    ticket=ticket,
                    actor=requester,
                    action="CREATED",
                    description="Ticket created",
                ),
                TicketHistory,
                opened,
            )

            if assigned is not None:
                _stamp(
                    TicketHistory.objects.create(
                        ticket=ticket,
                        actor=assigned,
                        action="ASSIGNED",
                        description=f"Assigned to {assigned.username}",
                    ),
                    TicketHistory,
                    first_reply_at - timedelta(minutes=5),
                )
                _stamp(
                    TicketComment.objects.create(
                        ticket=ticket,
                        author=assigned,
                        message=random.choice(AGENT_REPLIES),
                        is_internal=False,
                    ),
                    TicketComment,
                    first_reply_at,
                )
                if random.random() < 0.5:
                    _stamp(
                        TicketComment.objects.create(
                            ticket=ticket,
                            author=requester,
                            message=random.choice(REQUESTER_FOLLOWUPS),
                            is_internal=False,
                        ),
                        TicketComment,
                        first_reply_at + timedelta(hours=1),
                    )

            if is_resolved:
                _stamp(
                    TicketComment.objects.create(
                        ticket=ticket,
                        author=assigned or requester,
                        message="This has now been resolved. Closing the ticket.",
                        is_internal=False,
                    ),
                    TicketComment,
                    resolved_at,
                )
                _stamp(
                    TicketHistory.objects.create(
                        ticket=ticket,
                        actor=assigned or requester,
                        action="STATUS_CHANGED",
                        description=f"Status changed to {status}",
                    ),
                    TicketHistory,
                    resolved_at,
                )

            created.append(ticket)

        return created

    # -- AI enrichment ----------------------------------------------------

    def _apply_ai(self, tickets):
        """Ask the real AI service to classify every seeded ticket.

        The service reads each ticket from MySQL, returns its prediction and
        writes its own ai_analyses row, so this leaves the database in the
        same state a live classification run would.
        """
        self.stdout.write("Calling the AI service for each ticket...")

        ok = 0
        failed = 0
        categories = set()

        for ticket in tickets:
            text = f"{ticket.subject}\n\n{ticket.description}".strip()
            changed = False

            try:
                result = call_classification_service(ticket.id, text)
                data = result.get("data") or {}
                if result.get("status") and data.get("category_id"):
                    ticket.category_id = data["category_id"]
                    ticket.ai_confidence = data.get("confidence")
                    categories.add(data.get("category_title"))
                    changed = True

                result = call_priority_service(ticket.id, text)
                data = result.get("data") or {}
                predicted = (data.get("priority") or "").lower()
                if result.get("status") and predicted in PRIORITY_MAP:
                    ticket.priority = PRIORITY_MAP[predicted]
                    changed = True

                result = call_sentiment_service(ticket.id)
                data = result.get("data") or {}
                predicted = (data.get("sentiment") or "").lower()
                if result.get("status") and predicted in SENTIMENT_MAP:
                    ticket.sentiment = SENTIMENT_MAP[predicted]
                    changed = True

            except AIServiceError as exc:
                failed += 1
                self.stderr.write(
                    self.style.WARNING(f"  {ticket.ticket_number}: {exc}")
                )
                continue

            if changed:
                ticket.save(update_fields=[
                    "category", "priority", "sentiment", "ai_confidence",
                ])
                if ticket.category_id and ticket.category.department_id:
                    Ticket.objects.filter(pk=ticket.pk).update(
                        department_id=ticket.category.department_id
                    )
                ok += 1

        self.stdout.write(self.style.SUCCESS(
            f"AI enrichment complete: {ok} tickets updated, {failed} failed, "
            f"{len(categories)} distinct categories predicted."
        ))

    # -- removal ----------------------------------------------------------

    def _flush(self):
        demo_users = User.objects.filter(username__startswith=DEMO_USER_PREFIX)
        tickets = Ticket.objects.filter(requester__in=demo_users)

        ticket_ids = list(tickets.values_list("id", flat=True))
        ticket_count = len(ticket_ids)
        user_count = demo_users.count()

        with transaction.atomic():
            if ticket_ids:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM ai_analyses WHERE ticket_id IN %s",
                        [tuple(ticket_ids)],
                    )
            tickets.delete()
            demo_users.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Removed {ticket_count} demo tickets and {user_count} demo users."
        ))
