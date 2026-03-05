export type AgeGroup = "6-9" | "10-13" | "14-17";

export type StoryStyle = "fairy_tale" | "adventure" | "sci_fi" | "comic_book";

export interface StoryScene {
  text: string;
  imageUrl?: string;
  imageBase64?: string;
  audioUrl?: string;
  audioBase64?: string;
}

export interface FactCheck {
  accuracy_rating?: number | string;
  summary?: string;
}

export interface Story {
  id: string;
  title: string;
  ageGroup: AgeGroup;
  style: StoryStyle;
  scenes: StoryScene[];
  glossary?: Record<string, string>;
  factCheck?: FactCheck;
  sourceTitle?: string;
  paperTitle?: string;
  fieldOfStudy?: string;
  authors?: string;
  version?: number;
  upvotes?: number;
  downvotes?: number;
  userVote?: "up" | "down";
  titleAudioBase64?: string;
  conclusionAudioBase64?: string;
  createdAt: string;
}

export interface GenerationRequest {
  paperUrl: string;
  ageGroup: AgeGroup;
  style: StoryStyle;
}

export type GenerationStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "complete"
  | "error";

export interface JobResponse {
  jobId: string;
  status: "processing" | "complete" | "error" | "timed_out";
  story?: Story;
  error?: string;
  currentStage?: number;
  totalStages?: number;
  stageLabel?: string;
  processingTimeMs?: number;
}

export interface JobHistoryItem {
  job_id: string;
  uid: string;
  status: string;
  current_stage: number;
  total_stages: number;
  stage_label: string;
  story_id: string;
  paper_url: string;
  age_group: string;
  style: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  processing_time_ms: number | null;
  error: string | null;
}

export interface JobHistoryResponse {
  jobs: JobHistoryItem[];
}

export interface VoteResponse {
  upvotes: number;
  downvotes: number;
  userVote: "up" | "down";
  flaggedForRegen: boolean;
}

export interface QuotaInfo {
  remaining: number;
  limit: number;
  isAnonymous: boolean;
}

export interface TopPapersResponse {
  [field: string]: {
    id: string;
    title: string;
    paperTitle: string;
    upvotes: number;
    downvotes: number;
    ageGroup: string;
    style: string;
    archive: string;
  }[];
}
