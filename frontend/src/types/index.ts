export type AgeGroup = "6-9" | "10-13" | "14-17";

export type StoryStyle = "fairy_tale" | "adventure" | "sci_fi" | "comic_book";

export interface StoryScene {
  text: string;
  imageUrl?: string;
  imageBase64?: string;
  audioUrl?: string;
  audioBase64?: string;
}

export interface Story {
  id: string;
  title: string;
  ageGroup: AgeGroup;
  style: StoryStyle;
  scenes: StoryScene[];
  glossary?: Record<string, string>;
  sourceTitle?: string;
  paperTitle?: string;
  fieldOfStudy?: string;
  authors?: string;
  version?: number;
  upvotes?: number;
  downvotes?: number;
  userVote?: "up" | "down";
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

export interface VoteResponse {
  upvotes: number;
  downvotes: number;
  userVote: "up" | "down";
  flaggedForRegen: boolean;
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
