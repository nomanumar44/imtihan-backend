"""Test the AI service directly from the command line.

Usage:
    python manage.py test_ai
    python manage.py test_ai "What is CSS exam?"
    python manage.py test_ai "Explain this MCQ" --context mcq
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.ai_service import get_ai_response


class Command(BaseCommand):
    help = 'Test AI service response'

    def add_arguments(self, parser):
        parser.add_argument(
            'message',
            nargs='?',
            default='What is CSS exam eligibility?',
            help='Message to send to AI'
        )
        parser.add_argument(
            '--context',
            default='general',
            choices=['general', 'mcq', 'exam-board', 'past-papers', 'blog'],
            help='Context type for the AI prompt'
        )

    def handle(self, *args, **options):
        message = options['message']
        context_type = options['context']

        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write(self.style.HTTP_INFO('AI SERVICE TEST'))
        self.stdout.write(self.style.HTTP_INFO('=' * 60))

        # Show which keys are configured
        self.stdout.write(f"\nMessage: {message}")
        self.stdout.write(f"Context: {context_type}")

        self.stdout.write("\n" + self.style.HTTP_INFO('API Key Status:'))
        groq = getattr(settings, 'GROQ_API_KEY', '')
        kimi = getattr(settings, 'KIMI_API_KEY', '')
        gemini = getattr(settings, 'GEMINI_API_KEY', '')

        self.stdout.write(f"  GROQ_API_KEY:    {'Configured' if groq else 'Missing'}")
        self.stdout.write(f"  KIMI_API_KEY:    {'Configured' if kimi else 'Missing'}")
        self.stdout.write(f"  GEMINI_API_KEY:  {'Configured' if gemini else 'Missing'}")

        if not (groq or kimi or gemini):
            self.stdout.write(self.style.ERROR("\nNo API keys found! Add them to your .env file."))
            return

        self.stdout.write("\n" + self.style.HTTP_INFO('Calling AI...'))
        self.stdout.write("-" * 60)

        messages = [{'role': 'user', 'content': message}]
        result = get_ai_response(messages=messages, mcq=None, context_type=context_type)

        self.stdout.write(f"\nResult: {result}")
        self.stdout.write("-" * 60)

        # Detect what happened
        if result == "The AI assistant is currently busy. Please try again in a few minutes.":
            self.stdout.write(self.style.ERROR("All providers failed (quota/auth/missing keys)."))
        elif result == "Connection error. Please try again.":
            self.stdout.write(self.style.ERROR("Network error connecting to AI provider."))
        elif result == "Something went wrong. Please try again in a moment.":
            self.stdout.write(self.style.ERROR("Unknown error from AI provider."))
        elif result.startswith('__'):
            self.stdout.write(self.style.ERROR(f"Internal error code: {result}"))
        else:
            self.stdout.write(self.style.SUCCESS("Success! AI returned a real response."))
