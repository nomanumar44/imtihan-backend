# Imtihan.pk — Entity Relationship Diagram

## ER Diagram (Text Format)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          IMTIHAN.PK DATABASE SCHEMA                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────────────────────────────────┐
│  auth_user       │         │  core_student                                │
│  (Django Built-in)│        │─────────────────────────────────────────────│
│──────────────────│         │  id          PK  INT                        │
│  id         PK   │◄────────│  user_id     FK  → auth_user.id (1:1)       │
│  username        │         │  phone           VARCHAR(20)                 │
│  email           │         │  city            VARCHAR(100)                │
│  password        │         │  province        VARCHAR(100)                │
│  first_name      │         │  avatar          ImageField                  │
│  last_name       │         │  created_at      DATETIME                    │
│  is_staff        │         │  updated_at      DATETIME                    │
│  is_active       │         └──────────────────────────────────────────────┘
│  date_joined     │
└──────┬───────────┘
       │
       │ 1                    ┌──────────────────────────────────────────────┐
       │                      │  core_exam                                   │
       ├──────────────────────│──────────────────────────────────────────────│
       │                      │  id           PK  INT                        │
       │                      │  name             VARCHAR(100)  UNIQUE       │
       │                      │  slug             SlugField     UNIQUE       │
       │                      │  badge_color      VARCHAR(10)                │
       │                      │  created_at       DATETIME                   │
       │                      │  updated_at       DATETIME                   │
       │                      └──────────┬───────────────────────────────────┘
       │                                 │ 1
       │              ┌──────────────────┼──────────────────────────────┐
       │              │ M                │ M                             │ M
       │   ┌──────────▼──────────┐  ┌───▼──────────────┐  ┌────────────▼────────────┐
       │   │  core_mcq           │  │  core_pastpaper  │  │  core_syllabus          │
       │   │─────────────────────│  │──────────────────│  │─────────────────────────│
       │   │  id         PK INT  │  │  id       PK INT │  │  id         PK INT      │
       │   │  question_text TEXT │  │  title    VARCHAR│  │  title      VARCHAR(300)│
       │   │  option_a   VARCHAR │  │  slug     SLUG   │  │  exam_id    FK→exam     │
       │   │  option_b   VARCHAR │  │  exam_id  FK→exam│  │  post_name  VARCHAR(200)│
       │   │  option_c   VARCHAR │  │  subject_id FK   │  │  content    TEXT        │
       │   │  option_d   VARCHAR │  │  year     INT    │  │  pdf_file   FileField   │
       │   │  correct_option CHAR│  │  pdf_file FILE   │  │  created_at DATETIME    │
       │   │  explanation TEXT   │  │  source_url URL  │  │  updated_at DATETIME    │
       │   │  exam_id    FK→exam │  │  status   ENUM   │  └─────────────────────────┘
       │   │  subject_id FK      │  │  created_by FK→  │
       │   │  past_paper_id FK   │  │    auth_user     │
       │   │  source_url URL     │  │  created_at DT   │
       │   │  status     ENUM    │  │  updated_at DT   │
       │   │  created_by FK      │  └──────────────────┘
       │   │  created_at DT      │
       │   │  updated_at DT      │
       │   └──────────┬──────────┘
       │              │ M
       │   ┌──────────▼──────────┐
       │   │  core_subject       │
       │   │─────────────────────│
       │   │  id       PK  INT   │
       │   │  name     VARCHAR   │
       │   │  slug     SlugField │
       │   │  created_at DT      │
       │   │  updated_at DT      │
       │   └─────────────────────┘
       │
       │ 1                         ┌──────────────────────────────────────────┐
       │                           │  core_joblisting                         │
       │                           │──────────────────────────────────────────│
       │                           │  id            PK  INT                   │
       │                           │  title             VARCHAR(300)          │
       │                           │  exam_id       FK  → core_exam.id        │
       │                           │  department        VARCHAR(200)          │
       │                           │  location          VARCHAR(200)          │
       │                           │  bps_grade         VARCHAR(50)           │
       │                           │  description       TEXT                  │
       │                           │  qualifications    TEXT                  │
       │                           │  last_date         DATE                  │
       │                           │  apply_link        URL                   │
       │                           │  status            ENUM (active/closed/  │
       │                           │                         upcoming)        │
       │                           │  created_at        DATETIME              │
       │                           │  updated_at        DATETIME              │
       │                           └──────────────────────────────────────────┘
       │
       │ 1                         ┌──────────────────────────────────────────┐
       │                           │  core_testresult                         │
       ├──────────────────────────►│──────────────────────────────────────────│
       │                           │  id                 PK  INT              │
       │                           │  student_id         FK  → auth_user.id   │
       │                           │  exam_id            FK  → core_exam.id   │
       │                           │  subject_id         FK  → core_subject.id│
       │                           │  total_questions        INT              │
       │                           │  correct_answers        INT              │
       │                           │  wrong_answers          INT              │
       │                           │  score_percent          DECIMAL(5,2)     │
       │                           │  time_taken_seconds     INT              │
       │                           │  created_at             DATETIME         │
       │                           └──────────────────────────────────────────┘
       │
       │ 1                         ┌──────────────────────────────────────────┐
       │                           │  core_activitylog                        │
       └──────────────────────────►│──────────────────────────────────────────│
                                   │  id            PK  INT                   │
                                   │  activity_type     ENUM                  │
                                   │  message           VARCHAR(500)          │
                                   │  color             VARCHAR(7)            │
                                   │  user_id       FK  → auth_user.id        │
                                   │  created_at        DATETIME              │
                                   └──────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  core_contactmessage  (no FK — standalone)                                   │
│──────────────────────────────────────────────────────────────────────────────│
│  id          PK  INT                                                         │
│  name            VARCHAR(200)                                                │
│  email           EmailField                                                  │
│  subject         ENUM (general/bug/content/partnership/other)                │
│  message         TEXT                                                        │
│  status          ENUM (unread/read/replied)                                  │
│  created_at      DATETIME                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Relationships Summary

| From | Relation | To | Via |
|---|---|---|---|
| `Student` | 1 ──── 1 | `auth_user` | `user_id` (OneToOne) |
| `MCQ` | M ──── 1 | `Exam` | `exam_id` FK |
| `MCQ` | M ──── 1 | `Subject` | `subject_id` FK |
| `MCQ` | M ──── 1 | `PastPaper` | `past_paper_id` FK (nullable) |
| `MCQ` | M ──── 1 | `auth_user` | `created_by` FK (nullable) |
| `PastPaper` | M ──── 1 | `Exam` | `exam_id` FK |
| `PastPaper` | M ──── 1 | `Subject` | `subject_id` FK (nullable) |
| `PastPaper` | M ──── 1 | `auth_user` | `created_by` FK (nullable) |
| `Syllabus` | M ──── 1 | `Exam` | `exam_id` FK |
| `JobListing` | M ──── 1 | `Exam` | `exam_id` FK (nullable) |
| `TestResult` | M ──── 1 | `auth_user` | `student_id` FK |
| `TestResult` | M ──── 1 | `Exam` | `exam_id` FK (nullable) |
| `TestResult` | M ──── 1 | `Subject` | `subject_id` FK (nullable) |
| `ActivityLog` | M ──── 1 | `auth_user` | `user_id` FK (nullable) |
| `ContactMessage` | — | standalone | no FK |

---

## Model Status Enums

| Model | Field | Choices |
|---|---|---|
| `MCQ` | `status` | `draft`, `published`, `flagged` |
| `PastPaper` | `status` | `draft`, `published` |
| `JobListing` | `status` | `active`, `closed`, `upcoming` |
| `ActivityLog` | `activity_type` | `mcq_added`, `paper_uploaded`, `job_posted`, `syllabus_updated`, `flagged`, `other` |
| `ContactMessage` | `status` | `unread`, `read`, `replied` |
| `ContactMessage` | `subject` | `general`, `bug`, `content`, `partnership`, `other` |

---

## Central Hub: `Exam`

`Exam` is the **central hub** of the schema. Nearly every content model links back to it:
- MCQs belong to an exam board
- Past papers belong to an exam board
- Syllabi belong to an exam board
- Jobs are posted by exam boards
- Test results are tagged to an exam board

`auth_user` (Django built-in) is the **identity hub** — students, test results, activity logs, MCQ authorship, and paper uploads all trace back to it.
