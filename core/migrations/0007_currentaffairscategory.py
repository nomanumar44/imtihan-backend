from django.db import migrations, models


DEFAULT_CATEGORIES = [
    {"name": "Current IG's of Police", "slug": "current-igs-of-police", "region": "pakistan", "keywords": "ig"},
    {"name": "Current Governors", "slug": "current-governors", "region": "pakistan", "keywords": "governor"},
    {"name": "Current Chief Justices", "slug": "current-chief-justices", "region": "pakistan", "keywords": "chief justice"},
    {"name": "Current Ambassadors", "slug": "current-ambassadors", "region": "pakistan", "keywords": "ambassador"},
    {"name": "Federal Ministers", "slug": "current-federal-ministers", "region": "pakistan", "keywords": "minister"},
    {"name": "Chief Ministers", "slug": "current-chief-ministers", "region": "pakistan", "keywords": "chief minister"},
    {"name": "KPK Ministers", "slug": "current-kpk-ministers", "region": "pakistan", "keywords": "kpk"},
    {"name": "Punjab Ministers", "slug": "current-punjab-ministers", "region": "pakistan", "keywords": "punjab"},
    {"name": "Balochistan Ministers", "slug": "current-balochistan-ministers", "region": "pakistan", "keywords": "balochistan"},
    {"name": "Sindh Ministers", "slug": "current-sindh-ministers", "region": "pakistan", "keywords": "sindh"},
    {"name": "Gilgit Baltistan Ministers", "slug": "gilgit-baltistan-ministers", "region": "pakistan", "keywords": "gilgit"},
    {"name": "Presidents & CEOs", "slug": "current-presidents-chairmen-ceos", "region": "pakistan", "keywords": "president"},
    {"name": "World Organizations", "slug": "world-organizations", "region": "world", "keywords": "organization"},
    {"name": "Capitals & Currencies", "slug": "world-capitals-currencies", "region": "world", "keywords": "capital"},
    {"name": "International Days", "slug": "international-days", "region": "world", "keywords": "day"},
    {"name": "Nobel Prize Winners", "slug": "nobel-prize-winners", "region": "world", "keywords": "nobel"},
    {"name": "Sports Affairs", "slug": "sports-current-affairs", "region": "world", "keywords": "sport"},
    {"name": "Technology & Science", "slug": "technology-science", "region": "world", "keywords": "science"},
    {"name": "World Politics", "slug": "world-politics", "region": "world", "keywords": "politic"},
    {"name": "Global Economy", "slug": "global-economy", "region": "world", "keywords": "economy"},
    {"name": "Famous Books & Authors", "slug": "famous-books-authors", "region": "world", "keywords": "author"},
    {"name": "International Awards", "slug": "international-awards", "region": "world", "keywords": "award"},
    {"name": "World Health", "slug": "world-health", "region": "world", "keywords": "health"},
    {"name": "Education & Universities", "slug": "education-universities", "region": "world", "keywords": "education"},
]


def seed_categories(apps, schema_editor):
    category_model = apps.get_model("core", "CurrentAffairsCategory")
    for sort_order, category in enumerate(DEFAULT_CATEGORIES, start=1):
        category_model.objects.update_or_create(
            slug=category["slug"],
            defaults={
                "name": category["name"],
                "region": category["region"],
                "keywords": category["keywords"],
                "sort_order": sort_order,
                "is_active": True,
            },
        )


def unseed_categories(apps, schema_editor):
    category_model = apps.get_model("core", "CurrentAffairsCategory")
    category_model.objects.filter(
        slug__in=[category["slug"] for category in DEFAULT_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_joblisting_syllabus"),
    ]

    operations = [
        migrations.CreateModel(
            name="CurrentAffairsCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("region", models.CharField(choices=[("pakistan", "Pakistan"), ("world", "World")], default="pakistan", max_length=20)),
                ("keywords", models.TextField(blank=True, default="", help_text="Comma-separated words/phrases used to match MCQ question text.")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Current Affairs Category",
                "verbose_name_plural": "Current Affairs Categories",
                "ordering": ["region", "sort_order", "name"],
            },
        ),
        migrations.RunPython(seed_categories, unseed_categories),
    ]
