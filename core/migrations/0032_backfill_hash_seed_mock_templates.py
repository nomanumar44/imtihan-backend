import hashlib
import re

from django.db import migrations


def _hash(text):
    normalized = ' '.join(re.findall(r'[a-z0-9؀-ۿ]+', (text or '').lower()))
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()


# The configs that used to be hard-coded in frontend_mock_test.
MOCK_TEMPLATES = [
    ('ppsc-patwari', 'PPSC Patwari Mock Test', 'ppsc', {
        'english': 20, 'general-knowledge': 20, 'pakistan-studies': 20,
        'islamic-studies': 10, 'computer-science': 20, 'mathematics': 10,
    }),
    ('fpsc-inspector-customs', 'FPSC Inspector Customs Mock Test', 'fpsc', {
        'english': 20, 'general-knowledge': 20, 'current-affairs': 20,
        'pakistan-studies': 10, 'islamic-studies': 10, 'everyday-science': 20,
    }),
    ('ppsc-sub-inspector', 'PPSC Sub Inspector Mock Test', 'ppsc', {
        'english': 40, 'computer-science': 40, 'general-knowledge': 20,
    }),
    ('ppsc-assistant', 'PPSC Assistant Mock Test', 'ppsc', {
        'english': 20, 'pakistan-studies': 10, 'general-knowledge': 30,
        'islamic-studies': 10, 'mathematics': 10, 'computer-science': 20,
    }),
]


def forwards(apps, schema_editor):
    MCQ = apps.get_model('core', 'MCQ')
    for mcq in MCQ.objects.only('id', 'question_text').iterator():
        MCQ.objects.filter(pk=mcq.pk).update(normalized_hash=_hash(mcq.question_text))

    Exam = apps.get_model('core', 'Exam')
    MockTestTemplate = apps.get_model('core', 'MockTestTemplate')
    for slug, title, exam_slug, breakdown in MOCK_TEMPLATES:
        MockTestTemplate.objects.get_or_create(slug=slug, defaults={
            'title': title,
            'exam': Exam.objects.filter(slug=exam_slug).first(),
            'duration_minutes': 100,
            'breakdown': breakdown,
        })


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_quality_mocks_privacy'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
