from django.db import migrations


def forwards(apps, schema_editor):
    """Questions with a source URL came from the scrapers; uploads can't be told apart now."""
    MCQ = apps.get_model('core', 'MCQ')
    MCQ.objects.exclude(source_url='').update(origin='scraped')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_mcq_origin_paper_post'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
