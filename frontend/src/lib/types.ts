export type LearningMode = "project" | "concept";

export type UserMilestoneStatus = "pending" | "completed";

export type ProjectDifficulty = "beginner" | "intermediate" | "advanced";

export interface UserRead {
  id: number;
  email: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface CourseRead {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  primary_label: string;
  secondary_label: string;
}

export interface CourseOptionRead {
  id: number;
  course_id: number;
  parent_id: number | null;
  name: string;
  slug: string;
}

export interface MilestoneRead {
  id: number;
  project_id: number;
  title: string;
  description: string;
  instructions: string;
  order_index: number;
  success_criteria: string;
  concepts: string[];
  questions: string[];
}

export interface ProjectRead {
  id: number;
  title: string;
  description: string;
  difficulty: ProjectDifficulty;
  course_id: number;
  primary_option_id: number;
  secondary_option_id: number;
  is_active: boolean;
}

export interface UserMilestoneRead {
  id: number;
  user_project_id: number;
  milestone_id: number;
  status: UserMilestoneStatus;
  completed_at: string | null;
  milestone: MilestoneRead | null;
}

export interface UserProjectRead {
  id: number;
  enrollment_id: number;
  project_id: number;
  status: string;
  created_at: string;
  project: ProjectRead | null;
  user_milestones: UserMilestoneRead[];
}

export interface EnrollmentRead {
  id: number;
  user_id: number;
  course_id: number;
  primary_option_id: number;
  secondary_option_id: number;
  learning_mode: LearningMode;
  assigned_project_id: number | null;
  created_at: string;
  course: CourseRead | null;
  primary_option: CourseOptionRead | null;
  secondary_option: CourseOptionRead | null;
  user_project: UserProjectRead | null;
  concept_session_id: number | null;
}

export interface EnrollmentDetail extends EnrollmentRead {
  assigned_project: ProjectRead | null;
  milestones: MilestoneRead[];
  user_milestones: UserMilestoneRead[];
}

export interface EnrollmentCreate {
  course_id: number;
  primary_option_id: number;
  secondary_option_id: number;
  learning_mode: LearningMode;
}

export interface SandboxFileEntry {
  path: string;
  is_dir: boolean;
  size: number | null;
}

export interface SandboxRunResult {
  exit_code: number;
  stdout: string;
  stderr: string;
  timed_out: boolean;
  argv: string[];
}

export interface SandboxTestResult {
  passed: number;
  failed: number;
  errors: number;
  exit_code: number;
  timed_out: boolean;
  output: string;
  summary: string;
  outcome: string;
}

export interface ConceptCardRead {
  id: number;
  user_project_id: number;
  milestone_id: number;
  name: string;
  why_it_matters: string;
  research_questions: string[];
  resources: { title: string; url: string }[];
  checkpoint: string;
  explanation: string;
}

export interface MentorTurnRead {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface LearnerStateRead {
  user_project_id: number;
  milestone_id: number;
  question_index: number;
  questions_passed: number;
  question_attempts: number;
  questions_total: number;
  current_question: string | null;
  attempts: Record<string, unknown>[];
  researched_concepts: string[];
  failed_at: Record<string, unknown>[];
  can_explain: string[];
  can_reproduce: boolean;
  help_received: number;
  questions_complete: boolean;
}

export interface CoachMessageResponse {
  intent: string;
  reply: string;
  hint_level: number | null;
  hint_blocked_reason: string | null;
  policy_flags: string[];
  cards: ConceptCardRead[];
  turns: MentorTurnRead[];
  current_question: string | null;
  answer_status: string | null;
  push_back: string | null;
  learner_state: LearnerStateRead | null;
}

export interface CoachStartResponse {
  status: string;
  user_project_id: number;
  session_id: number;
  milestone_id: number | null;
  assessment_questions: { concept: string; prompt: string }[];
  roadmap: {
    milestone_id: number;
    title: string;
    order_index: number;
    concepts: { name: string; teaching: string; mastery: string }[];
  }[];
  cards: ConceptCardRead[];
  reply: string | null;
  current_question: string | null;
  answer_status: string | null;
  resumed: boolean;
  learner_state: LearnerStateRead | null;
}

export interface MilestoneReviewRead {
  id: number;
  user_milestone_id: number;
  verdict: "pending" | "passed" | "needs_work";
  dimensions: Record<string, { rating: string; notes: string }>;
  summary: string;
  understanding_questions: string[];
  understanding_answers: {
    question: string;
    answer: string;
    passed: boolean;
    feedback: string | null;
  }[];
  attempts: number;
  created_at: string;
  updated_at: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
