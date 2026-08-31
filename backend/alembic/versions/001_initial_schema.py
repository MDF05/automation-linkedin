"""001_initial_schema

Initial database schema: posts, bot_logs, interactions, job_applications,
ai_usage, schedules, settings (with seed data).

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ

# revision identifiers, used by Alembic
revision: str = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ posts
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "is_thread",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("thread_parts", JSONB(), nullable=True),
        sa.Column("thread_count", sa.Integer(), server_default=sa.text("1")),
        sa.Column("scheduled_at", TIMESTAMPTZ(), nullable=True),
        sa.Column("posted_at", TIMESTAMPTZ(), nullable=True),
        sa.Column("likes", sa.Integer(), server_default=sa.text("0")),
        sa.Column("comments", sa.Integer(), server_default=sa.text("0")),
        sa.Column("shares", sa.Integer(), server_default=sa.text("0")),
        sa.Column("ai_provider_used", sa.String(50), nullable=True),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column("search_references", JSONB(), nullable=True),
        sa.Column("linkedin_post_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_posts"),
        sa.CheckConstraint(
            "content_type IN ("
            "'storytelling','tips_list','pertanyaan','kutipan',"
            "'video_script','thread','promo','promo_portofolio','promo_testimoni'"
            ")",
            name="ck_posts_content_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','scheduled','posted','failed')",
            name="ck_posts_status",
        ),
    )
    op.create_index("idx_posts_status", "posts", ["status"])
    op.create_index("idx_posts_created_at", "posts", [sa.text("created_at DESC")])

    # --------------------------------------------------------------- bot_logs
    op.create_table(
        "bot_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(10), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bot_logs"),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], ondelete="SET NULL", name="fk_bot_logs_post_id"
        ),
        sa.CheckConstraint(
            "action IN ("
            "'generate_content','search_reference','generate_image',"
            "'open_linkedin','navigate_post','type_content','upload_image',"
            "'publish_post','screenshot','scroll_feed','read_ocr',"
            "'generate_comment','post_comment','open_jobs','search_jobs',"
            "'extract_jobs','easy_apply','fill_form','open_ai_web',"
            "'paste_prompt','copy_response','detect_captcha',"
            "'idle_wait','anti_ban_delay'"
            ")",
            name="ck_bot_logs_action",
        ),
        sa.CheckConstraint(
            "status IN ('success','failed','running','skipped','timeout')",
            name="ck_bot_logs_status",
        ),
    )
    op.create_index("idx_bot_logs_task_id", "bot_logs", ["task_id"])
    op.create_index(
        "idx_bot_logs_created_at", "bot_logs", [sa.text("created_at DESC")]
    )

    # ------------------------------------------------------------ interactions
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_post_url", sa.Text(), nullable=False),
        sa.Column("target_author", sa.String(255), nullable=True),
        sa.Column("target_post_text", sa.Text(), nullable=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("content_sent", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("skip_reason", sa.String(100), nullable=True),
        sa.Column("ai_provider_used", sa.String(50), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_interactions"),
        sa.CheckConstraint(
            "action_type IN ('comment','react','share','connect')",
            name="ck_interactions_action_type",
        ),
        sa.CheckConstraint(
            "status IN ('success','failed','skipped')",
            name="ck_interactions_status",
        ),
    )
    op.create_index(
        "idx_interactions_target_url", "interactions", ["target_post_url"]
    )
    op.create_index(
        "idx_interactions_created_at",
        "interactions",
        [sa.text("created_at DESC")],
    )

    # -------------------------------------------------------- job_applications
    op.create_table(
        "job_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("salary_range", sa.String(100), nullable=True),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(40),
            nullable=False,
            server_default=sa.text("'found'"),
        ),
        sa.Column(
            "has_easy_apply", sa.Boolean(), server_default=sa.text("false")
        ),
        sa.Column("job_type", sa.String(30), nullable=True),
        sa.Column("applied_at", TIMESTAMPTZ(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("form_fields_filled", JSONB(), nullable=True),
        sa.Column("search_session_id", sa.String(36), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_applications"),
        sa.UniqueConstraint("job_url", name="uq_job_applications_job_url"),
        sa.CheckConstraint(
            "status IN ("
            "'found','applied','skipped','rejected',"
            "'interview','offer',"
            "'skipped_incomplete_form','skipped_no_easy_apply'"
            ")",
            name="ck_job_applications_status",
        ),
    )
    op.create_index("idx_jobs_status", "job_applications", ["status"])
    op.create_index(
        "idx_jobs_created_at", "job_applications", [sa.text("created_at DESC")]
    )

    # ---------------------------------------------------------------- ai_usage
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_estimate",
            sa.Numeric(10, 6),
            server_default=sa.text("0"),
        ),
        sa.Column("module", sa.String(10), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_usage"),
        sa.CheckConstraint(
            "provider IN ("
            "'deepseek','groq','chatgpt_web','claude_web','perplexity_web'"
            ")",
            name="ck_ai_usage_provider",
        ),
    )
    op.create_index("idx_ai_usage_provider", "ai_usage", ["provider"])
    op.create_index(
        "idx_ai_usage_created_at", "ai_usage", [sa.text("created_at DESC")]
    )

    # --------------------------------------------------------------- schedules
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("scheduled_once_at", TIMESTAMPTZ(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_run", TIMESTAMPTZ(), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("next_run", TIMESTAMPTZ(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer(), server_default=sa.text("3")),
        sa.Column(
            "config_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("run_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("failure_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column(
            "created_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedules"),
        sa.CheckConstraint(
            "task_type IN ('post_konten','engage','job_hunt','promosi')",
            name="ck_schedules_task_type",
        ),
    )
    op.create_index("idx_schedules_active", "schedules", ["is_active"])
    op.create_index("idx_schedules_next_run", "schedules", ["next_run"])

    # --------------------------------------------------------------- settings
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_settings"),
        sa.UniqueConstraint("key", name="uq_settings_key"),
    )
    op.create_index("idx_settings_key", "settings", ["key"])

    # ------------------------------------------------ seed default settings
    op.execute(
        sa.text(
            """
            INSERT INTO settings (key, value, description) VALUES
            ('ai_provider_chain',
             '["deepseek","groq","chatgpt_web","claude_web"]',
             'Urutan provider AI dengan fallback otomatis'),
            ('ai_usage_limits',
             '{"deepseek":500000,"groq":30000,"chatgpt_web":100,"claude_web":50,"perplexity_web":50}',
             'Batas token atau request per bulan per provider'),
            ('anti_ban_limits',
             '{"posts_per_day":3,"comments_per_day":15,"applies_per_day":20}',
             'Batas aksi per hari per modul untuk anti-ban'),
            ('anti_ban_delays',
             '{"tap_min_ms":1000,"tap_max_ms":3000,"nav_min_ms":2000,"nav_max_ms":5000}',
             'Range delay antar aksi ADB dalam milidetik'),
            ('content_language',
             '"indonesia"',
             'Bahasa default untuk konten yang dihasilkan AI'),
            ('cv_path',
             'null',
             'Path file CV untuk fitur Easy Apply'),
            ('screenshot_enabled',
             'true',
             'Aktifkan screenshot setelah setiap aksi bot')
            ON CONFLICT (key) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("schedules")
    op.drop_table("ai_usage")
    op.drop_table("job_applications")
    op.drop_table("interactions")
    op.drop_table("bot_logs")
    op.drop_table("posts")
