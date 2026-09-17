import { clearToken, getToken } from "./auth-token";
import type {
  AdminConceptSpec,
  AdminGenerateRequest,
  AdminGraphPayload,
  AdminGraphSummary,
  AdminGenerateJob,
  CoachMessageResponse,
  CoachStartResponse,
  CourseOptionRead,
  CourseRead,
  EnrollmentCreate,
  EnrollmentDetail,
  EnrollmentRead,
  GraphRead,
  MilestoneCoachRead,
  MentorSessionRead,
  MentorSessionSummary,
  MilestoneReviewRead,
  ProjectDefenseRead,
  SandboxFileEntry,
  SandboxRunResult,
  SandboxTestResult,
  Token,
  UserRead,
} from "./types";
import { ApiError } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

function sandboxFilePath(filePath: string): string {
  return filePath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  auth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = true, headers, ...rest } = options;
  const hdrs = new Headers(headers);
  if (body !== undefined && !hdrs.has("Content-Type")) {
    hdrs.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (token) hdrs.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: hdrs,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth) {
    clearToken();
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(
      typeof detail === "string" ? detail : res.statusText,
      res.status,
      detail,
    );
  }

  return data as T;
}

async function pollAdminGenerateJob(
  payload: AdminGenerateRequest,
): Promise<AdminGraphPayload> {
  const started = await request<AdminGenerateJob>("/api/v1/admin/graphs/generate/jobs", {
    method: "POST",
    auth: false,
    body: payload,
  });
  const deadline = Date.now() + 10 * 60 * 1000;
  let jobId = started.job_id;
  while (Date.now() < deadline) {
    const job = await request<AdminGenerateJob>(
      `/api/v1/admin/graphs/generate/jobs/${jobId}`,
      { auth: false },
    );
    jobId = job.job_id || jobId;
    if (job.status === "done" && job.graph) {
      return job.graph;
    }
    if (job.status === "error") {
      throw new ApiError(job.error || "Could not generate a graph", 502, job.error);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new ApiError(
    "Graph generation is still running. Keep this tab open and try Generate again in a minute.",
    504,
  );
}

export const api = {
  register(email: string, password: string) {
    return request<UserRead>("/api/v1/auth/register", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
  },

  async login(email: string, password: string): Promise<Token> {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new ApiError(data.detail ?? "Login failed", res.status, data.detail);
    }
    return data as Token;
  },

  me() {
    return request<UserRead>("/api/v1/auth/me");
  },

  listCourses() {
    return request<CourseRead[]>("/api/v1/courses", { auth: false });
  },

  listPrimaryOptions(courseId: number) {
    return request<CourseOptionRead[]>(`/api/v1/courses/${courseId}/options`, {
      auth: false,
    });
  },

  listSecondaryOptions(courseId: number, primaryOptionId: number) {
    return request<CourseOptionRead[]>(
      `/api/v1/courses/${courseId}/options/${primaryOptionId}/options`,
      { auth: false },
    );
  },

  createEnrollment(payload: EnrollmentCreate) {
    return request<EnrollmentDetail>("/api/v1/enrollments", {
      method: "POST",
      body: payload,
    });
  },

  listEnrollments() {
    return request<EnrollmentRead[]>("/api/v1/enrollments");
  },

  getEnrollment(id: number) {
    return request<EnrollmentDetail>(`/api/v1/enrollments/${id}`);
  },

  getProject(projectId: number) {
    return request<import("./types").ProjectDetail>(
      `/api/v1/projects/${projectId}`,
      { auth: false },
    );
  },

  initSandbox(userProjectId: number) {
    return request<{ id: number; user_project_id: number; status: string }>(
      `/api/v1/me/projects/${userProjectId}/sandbox`,
      { method: "POST" },
    );
  },

  listSandboxFiles(userProjectId: number) {
    return request<{ files: SandboxFileEntry[] }>(
      `/api/v1/me/projects/${userProjectId}/sandbox/files`,
    );
  },

  readSandboxFile(userProjectId: number, filePath: string) {
    return request<{ path: string; content: string }>(
      `/api/v1/me/projects/${userProjectId}/sandbox/files/${sandboxFilePath(filePath)}`,
    );
  },

  writeSandboxFile(userProjectId: number, filePath: string, content: string) {
    return request<{ path: string; content: string }>(
      `/api/v1/me/projects/${userProjectId}/sandbox/files/${sandboxFilePath(filePath)}`,
      { method: "PUT", body: { content } },
    );
  },

  runSandbox(
    userProjectId: number,
    payload: { argv?: string[]; command?: string; cwd?: string | null },
  ) {
    return request<SandboxRunResult>(
      `/api/v1/me/projects/${userProjectId}/sandbox/run`,
      { method: "POST", body: payload },
    );
  },

  testSandbox(userProjectId: number) {
    return request<SandboxTestResult>(
      `/api/v1/me/projects/${userProjectId}/sandbox/test`,
      { method: "POST" },
    );
  },

  coachStart(userProjectId: number) {
    return request<CoachStartResponse>(
      `/api/v1/me/projects/${userProjectId}/coach/start`,
      { method: "POST", body: { answers: [] } },
    );
  },

  coachMessage(userProjectId: number, message: string) {
    return request<CoachMessageResponse>(
      `/api/v1/me/projects/${userProjectId}/coach/message`,
      { method: "POST", body: { message } },
    );
  },

  evaluatePractice(
    userProjectId: number,
    payload?: { filename?: string; task_id?: string },
  ) {
    return request<CoachMessageResponse>(
      `/api/v1/me/projects/${userProjectId}/coach/evaluate-practice`,
      { method: "POST", body: payload ?? {} },
    );
  },

  listCoachSessions(userProjectId: number) {
    return request<MentorSessionSummary[]>(
      `/api/v1/me/projects/${userProjectId}/coach/sessions`,
    );
  },

  getCoachSession(sessionId: number) {
    return request<MentorSessionRead>(`/api/v1/me/coach/sessions/${sessionId}`);
  },

  getMilestoneCoach(userMilestoneId: number, attempt?: number) {
    const query = attempt != null ? `?attempt=${attempt}` : "";
    return request<MilestoneCoachRead>(
      `/api/v1/me/milestones/${userMilestoneId}/coach${query}`,
    );
  },

  requestHint(userMilestoneId: number) {
    return request<CoachMessageResponse>(
      `/api/v1/me/milestones/${userMilestoneId}/hints`,
      { method: "POST" },
    );
  },

  getLearnerState(userProjectId: number) {
    return request<import("./types").LearnerStateRead>(
      `/api/v1/me/projects/${userProjectId}/state`,
    );
  },

  requestMilestoneReview(userMilestoneId: number) {
    return request<MilestoneReviewRead>(
      `/api/v1/me/milestones/${userMilestoneId}/review`,
      { method: "POST" },
    );
  },

  getMilestoneReview(userMilestoneId: number) {
    return request<MilestoneReviewRead>(
      `/api/v1/me/milestones/${userMilestoneId}/review`,
    );
  },

  answerMilestoneReview(userMilestoneId: number, answers: string[]) {
    return request<MilestoneReviewRead>(
      `/api/v1/me/milestones/${userMilestoneId}/review/answer`,
      { method: "POST", body: { answers } },
    );
  },

  getGraph(userProjectId: number) {
    return request<GraphRead>(`/api/v1/me/projects/${userProjectId}/graph`);
  },

  submitResearch(
    userProjectId: number,
    conceptId: string,
    payload: {
      question?: string;
      sources?: { title?: string; url?: string }[];
      learner_notes?: string;
      learner_summary?: string;
      remaining_questions?: string;
    },
  ) {
    return request(
      `/api/v1/me/projects/${userProjectId}/concepts/${conceptId}/research`,
      { method: "POST", body: payload },
    );
  },

  submitExplanation(userProjectId: number, conceptId: string, answer: string) {
    return request(
      `/api/v1/me/projects/${userProjectId}/concepts/${conceptId}/explain`,
      { method: "POST", body: { answer } },
    );
  },

  skipDiagnostic(userProjectId: number, conceptId: string, answers: string[]) {
    return request(
      `/api/v1/me/projects/${userProjectId}/concepts/${conceptId}/skip-diagnostic`,
      { method: "POST", body: { answers } },
    );
  },

  submitReflection(userMilestoneId: number, answers: Record<string, string>) {
    return request(`/api/v1/me/milestones/${userMilestoneId}/reflection`, {
      method: "POST",
      body: { answers },
    });
  },

  startDefense(userProjectId: number) {
    return request<ProjectDefenseRead>(
      `/api/v1/me/projects/${userProjectId}/defense/start`,
      {
        method: "POST",
      },
    );
  },

  answerDefense(userProjectId: number, answers: string[]) {
    return request<ProjectDefenseRead>(
      `/api/v1/me/projects/${userProjectId}/defense/answer`,
      {
        method: "POST",
        body: { answers },
      },
    );
  },

  listRetrievalChecks(userProjectId: number) {
    return request(`/api/v1/me/projects/${userProjectId}/retrieval-checks`);
  },

  answerRetrieval(userProjectId: number, checkId: number, answer: string) {
    return request(
      `/api/v1/me/projects/${userProjectId}/retrieval-checks/${checkId}/answer`,
      { method: "POST", body: { answer } },
    );
  },

  completeMilestone(userMilestoneId: number) {
    return request<import("./types").UserMilestoneRead>(
      `/api/v1/me/milestones/${userMilestoneId}/complete`,
      { method: "POST" },
    );
  },

  restartMilestone(userMilestoneId: number) {
    return request<import("./types").UserProjectRead>(
      `/api/v1/me/milestones/${userMilestoneId}/restart`,
      { method: "POST" },
    );
  },

  listAdminGraphs() {
    return request<AdminGraphSummary[]>("/api/v1/admin/graphs", { auth: false });
  },

  getAdminGraph(projectId: number) {
    return request<AdminGraphPayload>(`/api/v1/admin/graphs/${projectId}`, {
      auth: false,
    });
  },

  generateAdminGraph(payload: AdminGenerateRequest) {
    return pollAdminGenerateJob(payload);
  },

  generateAdminConcept(payload: {
    concept: Partial<AdminConceptSpec> & { id: string; title: string };
    language: string;
    project_title: string;
    slug: string;
  }) {
    return request<AdminConceptSpec>("/api/v1/admin/graphs/concepts/generate", {
      method: "POST",
      auth: false,
      body: payload,
    });
  },

  publishAdminGraph(payload: AdminGraphPayload) {
    return request<AdminGraphPayload>("/api/v1/admin/graphs", {
      method: "POST",
      auth: false,
      body: payload,
    });
  },

  updateAdminGraph(projectId: number, payload: AdminGraphPayload) {
    return request<AdminGraphPayload>(`/api/v1/admin/graphs/${projectId}`, {
      method: "PUT",
      auth: false,
      body: payload,
    });
  },
};
