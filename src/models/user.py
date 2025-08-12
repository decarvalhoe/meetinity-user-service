from datetime import datetime, timezone
from sqlalchemy import Index
from . import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120))
    company = db.Column(db.String(120))
    bio = db.Column(db.String(2000))
    skills = db.Column(db.String(500))
    interests = db.Column(db.String(500))
    location = db.Column(db.String(120))
    experience_years = db.Column(db.Integer, default=0)
    industry = db.Column(db.String(120))
    linkedin_url = db.Column(db.String(255))
    photo_url = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_users_industry_location', 'industry', 'location'),
        Index('idx_users_created_at', 'created_at'),
    )

    def skills_list(self):
        if not self.skills:
            return []
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    def interests_list(self):
        if not self.interests:
            return []
        return [s.strip() for s in self.interests.split(',') if s.strip()]
