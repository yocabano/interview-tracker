from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime
from sqlalchemy.sql import func
from database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=True)
    company = Column(String, nullable=False)
    position = Column(String, nullable=False)
    job_description = Column(Text, nullable=True)
    required_skills = Column(Text, nullable=True)  # comma-separated
    visa_sponsorship = Column(String, default="unknown")  # yes / no / unknown
    location = Column(String, nullable=True)
    remote_type = Column(String, nullable=True)  # remote / hybrid / onsite
    salary_range = Column(String, nullable=True)
    applied_date = Column(Date, nullable=True)
    status = Column(String, default="interested")
    # interested / applied / phone_screen / technical / onsite / offer / rejected / withdrawn
    interview_received = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
