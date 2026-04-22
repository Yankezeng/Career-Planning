from pathlib import Path
import sys

from sqlalchemy import delete, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.models.auth import EnterpriseProfile, Role, User
from app.models.career import CareerGoal, CareerPath, CareerPathTask, OptimizationRecord, Report, ResumeDelivery
from app.models.job import JobMatchGap, JobMatchResult
from app.models.student import (
    GrowthRecord,
    ReviewRecord,
    Student,
    StudentAttachment,
    StudentCampusExperience,
    StudentCertificate,
    StudentCompetition,
    StudentInternship,
    StudentProfile,
    StudentProject,
    StudentSkill,
)


KEEP_USERNAMES = {"admin", "student01", "enterprise01"}


def _collect_ids(db):
    users = db.scalars(select(User).order_by(User.id)).all()
    remove_users = [user for user in users if user.username not in KEEP_USERNAMES]
    remove_user_ids = [user.id for user in remove_users]

    student_ids = []
    attachment_ids = []
    growth_ids = []
    match_result_ids = []
    career_path_ids = []
    enterprise_profile_ids = []
    enterprise_user_ids = []

    if remove_user_ids:
        student_ids = db.scalars(select(Student.id).where(Student.user_id.in_(remove_user_ids))).all()
        if student_ids:
            attachment_ids = db.scalars(select(StudentAttachment.id).where(StudentAttachment.student_id.in_(student_ids))).all()
            growth_ids = db.scalars(select(GrowthRecord.id).where(GrowthRecord.student_id.in_(student_ids))).all()
            match_result_ids = db.scalars(select(JobMatchResult.id).where(JobMatchResult.student_id.in_(student_ids))).all()
            career_path_ids = db.scalars(select(CareerPath.id).where(CareerPath.student_id.in_(student_ids))).all()

        enterprise_rows = db.scalars(select(EnterpriseProfile).where(EnterpriseProfile.user_id.in_(remove_user_ids))).all()
        enterprise_profile_ids = [row.id for row in enterprise_rows]
        enterprise_user_ids = [row.user_id for row in enterprise_rows if row.user_id]

    return {
        "remove_users": remove_users,
        "remove_user_ids": remove_user_ids,
        "student_ids": student_ids,
        "attachment_ids": attachment_ids,
        "growth_ids": growth_ids,
        "match_result_ids": match_result_ids,
        "career_path_ids": career_path_ids,
        "enterprise_profile_ids": enterprise_profile_ids,
        "enterprise_user_ids": enterprise_user_ids,
    }


def cleanup_personnel_accounts():
    db = SessionLocal()
    try:
        ids = _collect_ids(db)
        remove_user_ids = ids["remove_user_ids"]
        if not remove_user_ids:
            print("No extra accounts found. Nothing to clean.")
            return

        student_ids = ids["student_ids"]
        attachment_ids = ids["attachment_ids"]
        growth_ids = ids["growth_ids"]
        match_result_ids = ids["match_result_ids"]
        career_path_ids = ids["career_path_ids"]
        enterprise_profile_ids = ids["enterprise_profile_ids"]
        enterprise_user_ids = ids["enterprise_user_ids"]

        if student_ids or enterprise_user_ids:
            conditions = []
            if student_ids:
                conditions.append(ReviewRecord.student_id.in_(student_ids))
            if enterprise_user_ids:
                conditions.append(ReviewRecord.enterprise_id.in_(enterprise_user_ids))
            for condition in conditions:
                db.execute(delete(ReviewRecord).where(condition))

        if student_ids:
            db.execute(delete(OptimizationRecord).where(OptimizationRecord.student_id.in_(student_ids)))
            db.execute(delete(Report).where(Report.student_id.in_(student_ids)))
            db.execute(delete(CareerGoal).where(CareerGoal.student_id.in_(student_ids)))

        if career_path_ids:
            db.execute(delete(CareerPathTask).where(CareerPathTask.career_path_id.in_(career_path_ids)))
            db.execute(delete(CareerPath).where(CareerPath.id.in_(career_path_ids)))

        if match_result_ids:
            db.execute(delete(JobMatchGap).where(JobMatchGap.match_result_id.in_(match_result_ids)))
            db.execute(delete(JobMatchResult).where(JobMatchResult.id.in_(match_result_ids)))

        if growth_ids:
            db.execute(delete(GrowthRecord).where(GrowthRecord.id.in_(growth_ids)))

        if student_ids or enterprise_profile_ids or attachment_ids:
            delivery_conditions = []
            if student_ids:
                delivery_conditions.append(ResumeDelivery.student_id.in_(student_ids))
            if enterprise_profile_ids:
                delivery_conditions.append(ResumeDelivery.enterprise_profile_id.in_(enterprise_profile_ids))
            if attachment_ids:
                delivery_conditions.append(ResumeDelivery.attachment_id.in_(attachment_ids))
            for condition in delivery_conditions:
                db.execute(delete(ResumeDelivery).where(condition))

        if attachment_ids:
            db.execute(delete(StudentAttachment).where(StudentAttachment.id.in_(attachment_ids)))

        if student_ids:
            db.execute(delete(StudentProfile).where(StudentProfile.student_id.in_(student_ids)))
            db.execute(delete(StudentSkill).where(StudentSkill.student_id.in_(student_ids)))
            db.execute(delete(StudentCertificate).where(StudentCertificate.student_id.in_(student_ids)))
            db.execute(delete(StudentProject).where(StudentProject.student_id.in_(student_ids)))
            db.execute(delete(StudentInternship).where(StudentInternship.student_id.in_(student_ids)))
            db.execute(delete(StudentCompetition).where(StudentCompetition.student_id.in_(student_ids)))
            db.execute(delete(StudentCampusExperience).where(StudentCampusExperience.student_id.in_(student_ids)))
            db.execute(delete(Student).where(Student.id.in_(student_ids)))

        if enterprise_profile_ids:
            db.execute(delete(EnterpriseProfile).where(EnterpriseProfile.id.in_(enterprise_profile_ids)))

        db.execute(delete(User).where(User.id.in_(remove_user_ids)))
        db.execute(delete(Role).where(Role.code.like("legacy_teacher_%")))

        db.commit()

        kept_users = db.scalars(select(User).order_by(User.id)).all()
        print("Cleanup completed.")
        print("Kept users:", [(user.id, user.username, user.role.code if user.role else None) for user in kept_users])
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_personnel_accounts()
