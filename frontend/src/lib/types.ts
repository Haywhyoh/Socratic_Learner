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

export interface ProjectDetail extends ProjectRead {
  objective: string;
  expected_outcome: string;
  prerequisites: string[];
  skills: string[];
  concepts: string[];
  constraints: string[];
  tests: string[];
  evaluation_criteria: string[];
  extension_challenges: string[];
  recommended_resources: { title: string; url: string }[];
  milestones: MilestoneRead[];
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
  cwd: string | null;
  mutates_fs: boolean;
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

export interface MentorTurnRead {
  id: number;
  role: "user" | "assistant" | "system" | "tutor" | "learner";
  content: string;
  created_at: string;
}

export type ConceptStatus =
  | "locked"
  | "available"
  | "introduced"
  | "researching"
  | "discussing"
  | "attempted"
  | "testing"
  | "blocked"
  | "diagnosis"
  | "knowledge_gap"
  | "explained"
  | "needs_review"
  | "verification"
  | "verified"
  | "mastered";

export interface LearnerStateRead {
  user_project_id: number | null;
  concept_id: string | null;
  status: ConceptStatus | string | null;
  evidence: Record<string, boolean>;
  attempt_count: number;
  hints_used: number;
  hint_level: number;
  last_explanation: string;
  milestone_id: number | null;
  user_milestone_id: number | null;
}

export interface MentorContractRead {
  intent: string;
  action: string;
  message: string;
  diagnostic_concept: string | null;
  identified_gap: { concept: string; confidence: number } | null;
  hint_level: number;
  should_unlock: boolean;
  next_state: string;
}

export interface GraphConceptRead {
  id: string;
  title: string;
  category: string;
  status: string;
  evidence: Record<string, boolean>;
}

export interface GraphMilestoneRead {
  user_milestone_id: number;
  milestone_id: number;
  title: string;
  order_index: number;
  status: string;
  description: string;
  success_criteria: string;
  concepts: GraphConceptRead[];
}

export interface GraphRead {
  user_project_id: number;
  project_id: number;
  current_milestone_id: number | null;
  current_user_milestone_id: number | null;
  current_concept_id: string | null;
  concept_state: string | null;
  project_complete: boolean;
  milestones: GraphMilestoneRead[];
  known_gaps: {
    id?: number;
    concept: string;
    status: string;
    suspected_gaps: { concept: string; confidence: number }[];
  }[];
  due_retrieval_checks: {
    id: number;
    concept_id: string;
    scheduled_for: string;
    prompt: string;
    status: string;
  }[];
}

export interface ConceptRead {
  id: string;
  title: string;
  category: string;
  description: string;
  learning_objectives: string[];
  misconceptions: string[];
  diagnostic_questions: string[];
  research_questions: string[];
  resources: { title: string; url: string }[];
  hints: string[];
  mastery_requirements: Record<string, boolean>;
}

export interface CoachMessageResponse {
  intent: string;
  action?: string;
  reply: string;
  hint_level: number | null;
  hint_blocked_reason: string | null;
  policy_flags: string[];
  cards: unknown[];
  turns: MentorTurnRead[];
  current_question: string | null;
  answer_status: string | null;
  push_back: string | null;
  learner_state: LearnerStateRead | null;
  contract: MentorContractRead | null;
  concept: ConceptRead | null;
}

export interface CoachStartResponse {
  status: string;
  user_project_id: number;
  session_id: number;
  milestone_id: number | null;
  assessment_questions: { concept: string; prompt: string }[];
  roadmap: unknown[];
  cards: unknown[];
  reply: string | null;
  current_question: string | null;
  answer_status: string | null;
  resumed: boolean;
  learner_state: LearnerStateRead | null;
  contract: MentorContractRead | null;
  concept: ConceptRead | null;
  graph: GraphRead | null;
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

export interface ProjectDefenseRead {
  id: number;
  user_project_id: number;
  questions: string[];
  answers: unknown[];
  verdict: string;
  summary: string;
  attempts: number;
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
