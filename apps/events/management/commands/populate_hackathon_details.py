"""
Management command to ensure all hackathons have full Overview & Guidelines,
Tracks & Themes, and Prizes & Awards filled.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event, Prize, Track


class Command(BaseCommand):
    help = "Populate missing Overview & Guidelines, Tracks, and Prizes for all hackathons."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(self.style.NOTICE("Ensuring all hackathon details (Overview, Tracks, Prizes) are populated..."))

        # Event: demo-ai-hackathon
        e2 = Event.objects.filter(slug='demo-ai-hackathon').first()
        if e2:
            e2.description = (
                "Welcome to the Demo AI Hackathon! This hackathon challenges developers, designers, and AI practitioners "
                "to build next-generation applications powered by generative AI, autonomous agent workflows, and intelligent interfaces.\n\n"
                "Challenge Overview:\n"
                "Explore how modern LLMs and intelligent agents can solve practical problems across industries—from developer tooling "
                "and enterprise workflow automation to education and multimodal user experiences.\n\n"
                "Eligibility & Rules:\n"
                "- Open to individuals and teams of up to 4 members.\n"
                "- Projects must be original work created during the hackathon window.\n"
                "- Both open-source foundation models and proprietary LLM APIs are permitted.\n"
                "- Teams may utilize existing open-source libraries, frameworks, and public datasets.\n\n"
                "Submission Requirements:\n"
                "- A public repository link containing well-documented source code and setup instructions.\n"
                "- A live deployment or runnable demonstration of your project.\n"
                "- A brief video or presentation explaining your architecture, agent loop, and user experience."
            )
            if not e2.start_date:
                e2.start_date = now - timedelta(days=2)
            if not e2.registration_deadline or e2.registration_deadline <= now:
                e2.registration_deadline = now + timedelta(days=5)
            if not e2.submission_deadline or e2.submission_deadline <= now:
                e2.submission_deadline = now + timedelta(days=7)
            if not e2.end_date:
                e2.end_date = now + timedelta(days=8)
            e2.save()

            e2_tracks = [
                ('Autonomous Agents & Multi-Agent Systems', 'Goal-directed agent loops, tool usage, retrieval-augmented memory, and multi-agent coordination.'),
                ('Enterprise Automation & Workflow Intelligence', 'Intelligent agents for document processing, compliance auditing, automated reporting, and enterprise systems integration.'),
                ('Multimodal Interfaces & Human-AI UX', 'Real-time voice, vision, dynamic canvases, and interactive reactive interfaces powered by frontier LLMs.'),
                ('Open Innovation & Social Impact', 'Accessible AI tools addressing education, healthcare, accessibility, and environmental sustainability.'),
            ]
            for name, desc in e2_tracks:
                Track.objects.update_or_create(event=e2, name=name, defaults={'description': desc})

            e2_prizes = [
                (1, 'Grand Champion', '$10,000 Cash + Cloud Credits'),
                (2, '1st Runner-Up', '$5,000 Cash'),
                (3, '2nd Runner-Up', '$2,500 Cash'),
                (4, 'Community Choice Award', '$1,000 Cash + Swag Bundle'),
            ]
            for rank, title, desc in e2_prizes:
                Prize.objects.update_or_create(event=e2, rank=rank, defaults={'title': title, 'description': desc})

            self.stdout.write(self.style.SUCCESS(f"Populated {e2.name}: {e2.tracks.count()} tracks, {e2.prizes.count()} prizes."))

        # Event: phase5-demo-hackathon
        e3 = Event.objects.filter(slug='phase5-demo-hackathon').first()
        if e3:
            e3.description = (
                "Welcome to the Phase 5 Demo Hackathon! This competition is dedicated to building robust, high-performance web applications, "
                "cloud-native microservices, and distributed systems.\n\n"
                "Challenge Overview:\n"
                "Design and implement production-ready architectures that emphasize reliability, sub-second latency, security, and exceptional "
                "developer experience. Showcase how modern cloud patterns and distributed systems handle real-world load.\n\n"
                "Eligibility & Rules:\n"
                "- Open to solo participants and squads of 1 to 4 members.\n"
                "- All code and configurations must be authored during the competition period.\n"
                "- Ensure API rate limits, secure credential handling, and privacy guidelines are followed.\n\n"
                "Submission Requirements:\n"
                "- Public GitHub/GitLab repository with a Dockerfile or docker-compose configuration.\n"
                "- A working live deployment accessible via public URL.\n"
                "- Comprehensive architectural documentation detailing data flow, security, and scalability.\n"
                "- A 3-minute video presentation demonstrating core user workflows."
            )
            if not e3.start_date:
                e3.start_date = now - timedelta(days=2)
            if not e3.registration_deadline or e3.registration_deadline <= now:
                e3.registration_deadline = now + timedelta(days=5)
            if not e3.submission_deadline or e3.submission_deadline <= now:
                e3.submission_deadline = now + timedelta(days=7)
            if not e3.end_date:
                e3.end_date = now + timedelta(days=8)
            e3.save()

            e3_tracks = [
                ('Cloud-Native & Distributed Architectures', 'Microservices, Kubernetes orchestration, event-driven streaming, and serverless compute.'),
                ('Real-Time Web & Collaborative Applications', 'WebSockets, WebRTC, real-time data sync, and multi-user collaborative experiences.'),
                ('DevOps, Security & Platform Engineering', 'Continuous delivery pipelines, zero-trust infrastructure, automated compliance, and observability.'),
                ('FinTech & High-Assurance Systems', 'High-throughput transaction processing, cryptographic ledgers, and fraud prevention architectures.'),
            ]
            for name, desc in e3_tracks:
                Track.objects.update_or_create(event=e3, name=name, defaults={'description': desc})

            e3_prizes = [
                (1, 'Grand Champion', '$10,000 Cash + Cloud Infrastructure Credits'),
                (2, '1st Runner-Up', '$5,000 Cash'),
                (3, '2nd Runner-Up', '$2,500 Cash'),
                (4, 'Best Cloud Architecture', '$1,500 Cloud Grant + Swag'),
            ]
            for rank, title, desc in e3_prizes:
                Prize.objects.update_or_create(event=e3, rank=rank, defaults={'title': title, 'description': desc})

            self.stdout.write(self.style.SUCCESS(f"Populated {e3.name}: {e3.tracks.count()} tracks, {e3.prizes.count()} prizes."))

        self.stdout.write(self.style.SUCCESS("All hackathon details are complete!"))
