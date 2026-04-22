CREATE DATABASE IF NOT EXISTS career_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE career_agent;

CREATE TABLE IF NOT EXISTS roles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  code VARCHAR(30) NOT NULL UNIQUE,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS departments (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS classes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  grade VARCHAR(30),
  department_id BIGINT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  real_name VARCHAR(50) NOT NULL,
  email VARCHAR(100),
  phone VARCHAR(30),
  is_active TINYINT(1) DEFAULT 1,
  role_id BIGINT NULL,
  department_id BIGINT NULL,
  class_id BIGINT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS students (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL UNIQUE,
  name VARCHAR(50) NOT NULL,
  gender VARCHAR(20),
  student_no VARCHAR(30) NOT NULL UNIQUE,
  grade VARCHAR(20),
  major VARCHAR(100),
  college VARCHAR(100),
  phone VARCHAR(30),
  email VARCHAR(100),
  interests JSON,
  target_industry VARCHAR(100),
  target_city VARCHAR(100),
  education_experience TEXT,
  bio TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_skills (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  level VARCHAR(30),
  category VARCHAR(50),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_certificates (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  issuer VARCHAR(100),
  issued_date VARCHAR(30),
  score VARCHAR(50),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_projects (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  role VARCHAR(100),
  description TEXT,
  technologies JSON,
  outcome TEXT,
  start_date VARCHAR(30),
  end_date VARCHAR(30),
  relevance_score DECIMAL(5,2) DEFAULT 75,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_internships (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  company VARCHAR(100) NOT NULL,
  position VARCHAR(100) NOT NULL,
  description TEXT,
  skills JSON,
  start_date VARCHAR(30),
  end_date VARCHAR(30),
  relevance_score DECIMAL(5,2) DEFAULT 75,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_competitions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  award VARCHAR(100),
  level VARCHAR(50),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_campus_experiences (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  title VARCHAR(100) NOT NULL,
  role VARCHAR(100),
  description TEXT,
  duration VARCHAR(50),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_attachments (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(255) NOT NULL,
  file_type VARCHAR(50),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL UNIQUE,
  category VARCHAR(100),
  industry VARCHAR(100),
  description TEXT,
  degree_requirement VARCHAR(100),
  major_requirement VARCHAR(255),
  internship_requirement VARCHAR(255),
  work_content TEXT,
  development_direction TEXT,
  salary_range VARCHAR(100),
  skill_weight DECIMAL(5,2) DEFAULT 0.40,
  certificate_weight DECIMAL(5,2) DEFAULT 0.10,
  project_weight DECIMAL(5,2) DEFAULT 0.20,
  soft_skill_weight DECIMAL(5,2) DEFAULT 0.10,
  core_skill_tags JSON,
  common_skill_tags JSON,
  certificate_tags JSON,
  job_profile JSON,
  generated_by_ai TINYINT(1) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_skills (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  job_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  importance INT DEFAULT 3,
  category VARCHAR(50),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_certificates (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  job_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  importance INT DEFAULT 3,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_relations (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_job_id BIGINT NOT NULL,
  target_job_id BIGINT NOT NULL,
  relation_type VARCHAR(50) NOT NULL,
  reason TEXT,
  related_skills JSON,
  recommended_courses JSON,
  recommended_certificates JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student_profiles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  professional_score DECIMAL(5,2) DEFAULT 0,
  practice_score DECIMAL(5,2) DEFAULT 0,
  communication_score DECIMAL(5,2) DEFAULT 0,
  learning_score DECIMAL(5,2) DEFAULT 0,
  innovation_score DECIMAL(5,2) DEFAULT 0,
  professionalism_score DECIMAL(5,2) DEFAULT 0,
  ability_tags JSON,
  strengths JSON,
  weaknesses JSON,
  maturity_level VARCHAR(50),
  summary TEXT,
  raw_metrics JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_match_results (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  job_id BIGINT NOT NULL,
  total_score DECIMAL(5,2) DEFAULT 0,
  major_match DECIMAL(5,2) DEFAULT 0,
  skill_match DECIMAL(5,2) DEFAULT 0,
  certificate_match DECIMAL(5,2) DEFAULT 0,
  project_match DECIMAL(5,2) DEFAULT 0,
  internship_match DECIMAL(5,2) DEFAULT 0,
  soft_skill_match DECIMAL(5,2) DEFAULT 0,
  interest_match DECIMAL(5,2) DEFAULT 0,
  reasons JSON,
  summary TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_match_gaps (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  match_result_id BIGINT NOT NULL,
  gap_type VARCHAR(50) NOT NULL,
  gap_item VARCHAR(150) NOT NULL,
  description TEXT,
  priority INT DEFAULT 3,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS career_goals (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  target_job_id BIGINT NULL,
  target_company_type VARCHAR(100),
  short_term_goal TEXT,
  medium_term_goal TEXT,
  mid_long_term_goal TEXT,
  long_term_goal TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS career_paths (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  target_job_id BIGINT NULL,
  based_on_match_id BIGINT NULL,
  overview TEXT,
  summary TEXT,
  status VARCHAR(30) DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS career_path_tasks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  career_path_id BIGINT NOT NULL,
  stage_label VARCHAR(50) NOT NULL,
  category VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  due_hint VARCHAR(100),
  priority INT DEFAULT 3,
  weekly_tasks JSON,
  related_skills JSON,
  difficulty_level VARCHAR(20) DEFAULT '中',
  is_completed TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reports (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  career_path_id BIGINT NULL,
  match_result_id BIGINT NULL,
  title VARCHAR(255) NOT NULL,
  summary TEXT,
  content_html LONGTEXT,
  content_json JSON,
  pdf_path VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS growth_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  stage_label VARCHAR(50) NOT NULL,
  completed_courses JSON,
  new_skills JSON,
  new_certificates JSON,
  new_projects JSON,
  new_internships JSON,
  weekly_summary TEXT,
  completion_rate DECIMAL(5,2) DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS review_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  growth_record_id BIGINT NULL,
  enterprise_id BIGINT NOT NULL,
  comment TEXT,
  score DECIMAL(5,2) DEFAULT 0,
  suggestions JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS optimization_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  based_on_growth_id BIGINT NULL,
  based_on_review_id BIGINT NULL,
  summary TEXT,
  suggestions JSON,
  new_profile_snapshot JSON,
  new_match_snapshot JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS system_configs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  `key` VARCHAR(100) NOT NULL UNIQUE,
  `value` TEXT NOT NULL,
  config_type VARCHAR(30),
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS enterprise_profiles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NULL UNIQUE,
  company_name VARCHAR(150) NOT NULL UNIQUE,
  company_code VARCHAR(100),
  industry VARCHAR(100),
  address VARCHAR(150),
  company_type VARCHAR(100),
  company_size VARCHAR(100),
  description TEXT,
  source_doc_ids JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resume_deliveries (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  attachment_id BIGINT NOT NULL,
  enterprise_profile_id BIGINT NOT NULL,
  knowledge_doc_id VARCHAR(100),
  target_job_name VARCHAR(150),
  target_job_category VARCHAR(100),
  match_score DECIMAL(5,2) DEFAULT 0,
  delivery_status VARCHAR(30) DEFAULT 'delivered',
  delivery_note TEXT,
  enterprise_feedback TEXT,
  snapshot JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by BIGINT NULL,
  updated_by BIGINT NULL,
  deleted TINYINT(1) DEFAULT 0
);
