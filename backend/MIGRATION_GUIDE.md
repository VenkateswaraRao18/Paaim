"""Production database schema and migrations guide.

This file documents the database schema and how to manage migrations
in a production PAAIM deployment.

Running Migrations:
  $ alembic upgrade head              # Apply all pending migrations
  $ alembic downgrade -1              # Rollback one migration
  $ alembic current                   # Show current migration version
  $ alembic history                   # Show all migrations

Creating New Migrations:
  $ alembic revision -m "description" # Create new migration
  $ alembic upgrade head              # Apply it

Connection String:
  postgresql://user:password@host:5432/paaim_db
"""

# Schema Overview

"""
Tables (created by SQLAlchemy ORM currently):
- audit_logs: Complete decision audit trails
- decisions: Manufacturing decisions
- events: Incoming manufacturing events
- factories: Manufacturing facility configuration
- approval_workflows: Human approval tracking
- connector_health_checks: Health monitoring data

Future Schema Enhancements (Phase 2.5):
- user_profiles: User accounts with JWT
- api_keys: Service authentication
- audit_events: User action audit trail
- system_configuration: Feature flags, settings
- connector_status: Real-time connector state
- metrics: Prometheus metrics snapshots
"""

# Sample Migration: Initial Schema (001_initial_schema.py)
"""
def upgrade():
    # Create audit_logs table with production indexes
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('decision_id', sa.String(64), sa.ForeignKey('decisions.id')),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('actor', sa.String(255)),
        sa.Column('action', sa.String(255)),
        sa.Column('details', sa.JSON),
        sa.Column('timestamp', sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, onupdate=datetime.utcnow),
    )
    
    # Production indexes for queries
    op.create_index('idx_audit_logs_decision_id', 'audit_logs', ['decision_id'])
    op.create_index('idx_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('idx_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('idx_audit_logs_actor', 'audit_logs', ['actor'])

def downgrade():
    op.drop_table('audit_logs')
"""

# Sample Migration: Add RBAC (002_add_rbac.py)
"""
def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('role', sa.String(50), default='viewer'),  # viewer, operator, supervisor, admin
        sa.Column('factory_id', sa.String(64), sa.ForeignKey('factories.id')),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, onupdate=datetime.utcnow),
    )
    
    # Create API keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id')),
        sa.Column('key_hash', sa.String(255), unique=True),
        sa.Column('name', sa.String(255)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('expires_at', sa.DateTime),
    )
    
    op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'])

def downgrade():
    op.drop_table('api_keys')
    op.drop_table('users')
"""

# Sample Migration: Add Metrics (003_add_metrics.py)
"""
def upgrade():
    op.create_table(
        'decision_metrics',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('decision_id', sa.String(64), sa.ForeignKey('decisions.id')),
        sa.Column('latency_ms', sa.Float),
        sa.Column('agents_latency_ms', sa.Float),
        sa.Column('policy_latency_ms', sa.Float),
        sa.Column('twin_latency_ms', sa.Float),
        sa.Column('red_team_latency_ms', sa.Float),
        sa.Column('approval_latency_ms', sa.Float),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
    )
    
    op.create_index('idx_decision_metrics_decision_id', 'decision_metrics', ['decision_id'])
    op.create_index('idx_decision_metrics_created_at', 'decision_metrics', ['created_at'])

def downgrade():
    op.drop_table('decision_metrics')
"""
