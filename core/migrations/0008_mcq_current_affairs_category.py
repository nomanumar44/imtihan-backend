from django.db import migrations, models
import django.db.models.deletion


def backfill_current_affairs_categories(apps, schema_editor):
    MCQ = apps.get_model('core', 'MCQ')
    CurrentAffairsCategory = apps.get_model('core', 'CurrentAffairsCategory')

    categories = list(
        CurrentAffairsCategory.objects
        .filter(is_active=True)
        .order_by('region', 'sort_order', 'name')
    )

    for mcq in MCQ.objects.filter(subject__slug='current-affairs', current_affairs_category__isnull=True):
        question = (mcq.question_text or '').lower()
        matched_category = None

        for category in categories:
            keywords = [item.strip().lower() for item in (category.keywords or '').split(',') if item.strip()]
            if not keywords:
                keywords = [category.slug.replace('-', ' ').lower()]
            if any(keyword in question for keyword in keywords):
                matched_category = category
                break

        if matched_category:
            mcq.current_affairs_category = matched_category
            mcq.save(update_fields=['current_affairs_category'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_currentaffairscategory'),
    ]

    operations = [
        migrations.AddField(
            model_name='mcq',
            name='current_affairs_category',
            field=models.ForeignKey(
                blank=True,
                help_text='Only used when subject is Current Affairs.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mcqs',
                to='core.currentaffairscategory',
            ),
        ),
        migrations.RunPython(backfill_current_affairs_categories, migrations.RunPython.noop),
    ]
